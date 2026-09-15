from __future__ import annotations

import json
import os
import queue
import subprocess
import tempfile
import threading
import time
from collections import deque
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Self, TextIO

EVENT_PREFIX = "__EMBODIED_SCENE_EVENT__"


class LocalWorkerSession:
    """A short-lived JSONL worker session that owns one loaded model."""

    def __init__(
        self,
        command: list[str],
        load_config: Mapping[str, Any],
        *,
        startup_timeout_seconds: float,
        generation_timeout_seconds: float,
        environment: Mapping[str, str] | None = None,
        environment_factory: Callable[[Path], Mapping[str, str]] | None = None,
        cwd: Path | None = None,
        popen_factory: Callable[..., Any] = subprocess.Popen,
        temporary_prefix: str = "local-model-",
    ) -> None:
        self.command = command
        self.load_config = dict(load_config)
        self.startup_timeout_seconds = startup_timeout_seconds
        self.generation_timeout_seconds = generation_timeout_seconds
        self.environment = dict(environment) if environment is not None else None
        self.environment_factory = environment_factory
        self.cwd = cwd
        self.popen_factory = popen_factory
        self.temporary_prefix = temporary_prefix
        self._temporary: tempfile.TemporaryDirectory[str] | None = None
        self._stderr: TextIO | None = None
        self._process: Any = None
        self._stdout_queue: queue.Queue[str | None] = queue.Queue()
        self._stdout_noise: deque[str] = deque(maxlen=20)
        self._reader: threading.Thread | None = None
        self._job_counter = 0

    @property
    def temporary_path(self) -> Path:
        if self._temporary is None:
            raise RuntimeError("Worker session has not been started")
        return Path(self._temporary.name)

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()

    def start(self) -> None:
        if self._process is not None:
            return
        self._temporary = tempfile.TemporaryDirectory(prefix=self.temporary_prefix)
        self._stderr = tempfile.TemporaryFile(  # noqa: SIM115 - closed by close/_abort
            mode="w+t", encoding="utf-8"
        )
        environment = (
            dict(self.environment_factory(self.temporary_path))
            if self.environment_factory is not None
            else self.environment
        )
        try:
            self._process = self.popen_factory(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self._stderr,
                text=True,
                bufsize=1,
                env=environment,
                cwd=str(self.cwd) if self.cwd else None,
            )
        except Exception:
            self._cleanup()
            raise
        if self._process.stdin is None or self._process.stdout is None:
            self._abort()
            raise RuntimeError("Local worker did not expose stdin and stdout")
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()
        try:
            self._send({"command": "load", "config": self.load_config})
            event = self._read_event(self.startup_timeout_seconds)
            if event.get("event") != "ready":
                raise RuntimeError(self._event_error(event, "failed to become ready"))
        except Exception:
            self._abort()
            raise

    def request(self, payload: Mapping[str, Any], *, job_id: str | None = None) -> dict:
        if self._process is None:
            raise RuntimeError("Worker session is not active")
        self._job_counter += 1
        resolved_job_id = job_id or f"job_{self._job_counter:04d}"
        self._send(
            {
                "command": "generate",
                "job_id": resolved_job_id,
                "request": dict(payload),
            }
        )
        try:
            event = self._read_event(self.generation_timeout_seconds)
        except TimeoutError:
            self._abort()
            raise
        if event.get("job_id") != resolved_job_id:
            self._abort()
            raise RuntimeError(
                f"Local worker returned job_id {event.get('job_id')!r}; "
                f"expected {resolved_job_id!r}"
            )
        if event.get("event") == "failed":
            raise RuntimeError(self._event_error(event, "generation failed"))
        if event.get("event") != "completed":
            self._abort()
            raise RuntimeError(f"Unexpected local worker event: {event!r}")
        return event

    def close(self) -> None:
        process = self._process
        if process is None:
            self._cleanup()
            return
        try:
            if process.poll() is None:
                self._send({"command": "close"})
                event = self._read_event(min(self.startup_timeout_seconds, 30.0))
                if event.get("event") != "closed":
                    raise RuntimeError(f"Unexpected local worker close event: {event!r}")
                process.wait(timeout=10)
        except (BrokenPipeError, RuntimeError, TimeoutError, subprocess.TimeoutExpired):
            self._terminate()
        finally:
            self._cleanup()

    def _send(self, message: Mapping[str, Any]) -> None:
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("Local worker session is not active")
        self._process.stdin.write(json.dumps(dict(message)) + "\n")
        self._process.stdin.flush()

    def _read_event(self, timeout_seconds: float) -> dict:
        if self._process is None or self._process.stdout is None:
            raise RuntimeError("Local worker session is not active")
        deadline = time.monotonic() + timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"Local worker did not respond within {timeout_seconds:g} seconds"
                )
            try:
                line = self._stdout_queue.get(timeout=remaining)
            except queue.Empty as error:
                raise TimeoutError(
                    f"Local worker did not respond within {timeout_seconds:g} seconds"
                ) from error
            if line is None:
                detail = (
                    self._stderr_text()
                    or "\n".join(self._stdout_noise)
                    or f"exit code {self._process.poll()}"
                )
                raise RuntimeError(f"Local worker exited unexpectedly: {detail}")
            marker = line.find(EVENT_PREFIX)
            if marker < 0:
                if noise := line.strip():
                    self._stdout_noise.append(noise[-500:])
                continue
            payload = line[marker + len(EVENT_PREFIX) :].strip()
            try:
                event = json.loads(payload)
            except json.JSONDecodeError as error:
                self._abort()
                raise RuntimeError(
                    f"Local worker emitted an invalid framed event: {payload}"
                ) from error
            if not isinstance(event, dict):
                self._abort()
                raise TypeError(f"Local worker event must be an object: {event!r}")
            return event

    def _read_stdout(self) -> None:
        if self._process is None or self._process.stdout is None:
            self._stdout_queue.put(None)
            return
        try:
            for line in self._process.stdout:
                self._stdout_queue.put(line)
        finally:
            self._stdout_queue.put(None)

    @staticmethod
    def _event_error(event: Mapping[str, Any], fallback: str) -> str:
        detail = event.get("error")
        return str(detail).strip() if detail else fallback

    def _stderr_text(self) -> str:
        if self._stderr is None:
            return ""
        self._stderr.flush()
        self._stderr.seek(0)
        return self._stderr.read().strip()

    def _terminate(self) -> None:
        if self._process is None or self._process.poll() is not None:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=5)

    def _abort(self) -> None:
        self._terminate()
        self._cleanup()

    def _cleanup(self) -> None:
        if self._process is not None:
            if self._process.stdin is not None:
                self._process.stdin.close()
            if self._reader is not None:
                self._reader.join(timeout=1)
            if self._process.stdout is not None:
                self._process.stdout.close()
            self._process = None
        self._reader = None
        self._stdout_queue = queue.Queue()
        self._stdout_noise.clear()
        if self._stderr is not None:
            self._stderr.close()
            self._stderr = None
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None


def child_environment(overrides: Mapping[str, str] | None = None) -> dict[str, str]:
    environment = os.environ.copy()
    if overrides:
        environment.update(overrides)
    return environment
