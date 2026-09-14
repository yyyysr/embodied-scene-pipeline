from __future__ import annotations

import base64
import mimetypes
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .http import HttpTransport, UrllibTransport
from .state import read_state, write_state


def file_data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


@dataclass(frozen=True)
class FalQueueResult:
    request_id: str
    data: dict


class FalQueueClient:
    """Resumable FAL queue protocol shared by image and 3D providers."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        transport: HttpTransport | None = None,
        poll_interval_seconds: float = 5.0,
        timeout_seconds: float = 900.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.api_key = api_key
        self.transport = transport or UrllibTransport()
        self.poll_interval_seconds = poll_interval_seconds
        self.timeout_seconds = timeout_seconds
        self.sleep = sleep
        self.clock = clock

    @property
    def headers(self) -> dict[str, str]:
        key = self.api_key or os.environ.get("FAL_KEY")
        if not key:
            raise RuntimeError("FAL_KEY is not set")
        return {"Authorization": f"Key {key}", "Content-Type": "application/json"}

    def run(self, endpoint: str, payload: dict, state_path: Path) -> FalQueueResult:
        state = read_state(state_path)
        if state:
            if state.get("endpoint") != endpoint or not state.get("request_id"):
                raise ValueError(f"Invalid resumable FAL state: {state_path}")
        else:
            submitted = self.transport.request_json(
                "POST",
                f"https://queue.fal.run/{endpoint}",
                headers=self.headers,
                payload=payload,
            )
            request_id = submitted.get("request_id")
            if not request_id:
                raise RuntimeError("FAL submit response did not include request_id")
            state = {
                "endpoint": endpoint,
                "request_id": request_id,
                "status_url": submitted.get("status_url"),
                "response_url": submitted.get("response_url"),
            }
            state = {key: value for key, value in state.items() if value is not None}
            write_state(state_path, state)

        request_id = str(state["request_id"])
        status_url = state.get("status_url") or (
            f"https://queue.fal.run/{endpoint}/requests/{request_id}/status"
        )
        deadline = self.clock() + self.timeout_seconds
        while True:
            status = self.transport.request_json("GET", status_url, headers=self.headers)
            status_name = str(status.get("status", "UNKNOWN")).upper()
            if status.get("error"):
                state_path.unlink(missing_ok=True)
                raise RuntimeError(f"FAL request failed: {status['error']}")
            if status_name == "COMPLETED":
                break
            if status_name in {"FAILED", "CANCELLED", "CANCELED"}:
                state_path.unlink(missing_ok=True)
                raise RuntimeError(f"FAL request ended with status {status_name}")
            if self.clock() >= deadline:
                raise TimeoutError(f"FAL request timed out; resume state kept at {state_path}")
            self.sleep(self.poll_interval_seconds)

        response_url = state.get("response_url") or (
            f"https://queue.fal.run/{endpoint}/requests/{request_id}"
        )
        result = self.transport.request_json("GET", response_url, headers=self.headers)
        return FalQueueResult(request_id, result)
