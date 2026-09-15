from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Self

from ._local_worker import LocalWorkerSession, child_environment
from .generation_3d import AssetGenerationRequest, GeneratedAssetResult
from .image_editing import validate_image_input


def _default_worker_path() -> Path:
    return Path(__file__).resolve().parents[3] / "local_runtime" / "trellis_worker.py"


def _default_repo_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "third_party" / "TRELLIS"


class LocalTrellisProvider:
    """Generate one textured GLB through an isolated local TRELLIS worker."""

    provider = "local"

    def __init__(
        self,
        *,
        python_executable: str | None = None,
        worker_path: Path | None = None,
        repo_dir: Path | None = None,
        model_id: str = "microsoft/TRELLIS-image-large",
        attention_backend: str = "flash-attn",
        spconv_algo: str = "native",
        seed: int = 42,
        sparse_structure_steps: int = 12,
        sparse_structure_guidance: float = 7.5,
        slat_steps: int = 12,
        slat_guidance: float = 3.0,
        simplify: float = 0.95,
        texture_size: int = 1024,
        timeout_seconds: float = 1800.0,
        run_command: Callable[..., Any] = subprocess.run,
    ):
        self.python_executable = (
            os.environ.get("EMBODIED_SCENE_LOCAL_TRELLIS_PYTHON")
            or python_executable
            or sys.executable
        )
        self.worker_path = (worker_path or _default_worker_path()).resolve()
        configured_repo = os.environ.get("EMBODIED_SCENE_TRELLIS_REPO_DIR")
        self.repo_dir = Path(configured_repo or repo_dir or _default_repo_dir()).resolve()
        self.model_id = model_id
        self.attention_backend = attention_backend
        self.spconv_algo = spconv_algo
        self.seed = seed
        self.sparse_structure_steps = sparse_structure_steps
        self.sparse_structure_guidance = sparse_structure_guidance
        self.slat_steps = slat_steps
        self.slat_guidance = slat_guidance
        self.simplify = simplify
        self.texture_size = texture_size
        self.timeout_seconds = timeout_seconds
        self.run_command = run_command

    def _validate(self, request: AssetGenerationRequest) -> Path:
        if not re.fullmatch(r"[a-z0-9_]+", request.asset_id):
            raise ValueError("asset_id must contain lowercase letters, digits, or underscores")
        if request.mode != "image-to-3d":
            raise ValueError("Local TRELLIS supports image-to-3d only")
        if len(request.reference_images) != 1:
            raise ValueError("Local TRELLIS requires exactly one reference image")
        if len(request.target_dimensions) != 3 or any(
            value <= 0 for value in request.target_dimensions
        ):
            raise ValueError("target_dimensions must contain three positive meter values")
        if not self.worker_path.is_file():
            raise FileNotFoundError(f"TRELLIS worker does not exist: {self.worker_path}")
        if not (self.repo_dir / "trellis").is_dir():
            raise FileNotFoundError(f"TRELLIS source is not initialized under: {self.repo_dir}")
        return validate_image_input(request.reference_images[0])

    def _model_config(self) -> dict:
        return {
            "model_id": self.model_id,
            "attention_backend": self.attention_backend,
            "spconv_algo": self.spconv_algo,
        }

    def _job_payload(self, input_path: Path, output_path: Path) -> dict:
        return {
            "input_path": str(input_path),
            "output_path": str(output_path),
            "seed": self.seed,
            "sparse_structure_steps": self.sparse_structure_steps,
            "sparse_structure_guidance": self.sparse_structure_guidance,
            "slat_steps": self.slat_steps,
            "slat_guidance": self.slat_guidance,
            "simplify": self.simplify,
            "texture_size": self.texture_size,
        }

    def _payload(self, input_path: Path, output_path: Path) -> dict:
        return self._model_config() | self._job_payload(input_path, output_path)

    def _environment(self, cache_root: Path) -> dict[str, str]:
        python_path = str(self.repo_dir)
        existing = os.environ.get("PYTHONPATH")
        if existing:
            python_path = os.pathsep.join((python_path, existing))
        return child_environment(
            {
                "PYTHONPATH": python_path,
                "NUMBA_CACHE_DIR": str(cache_root / "numba"),
                "WARP_CACHE_PATH": str(cache_root / "warp"),
            }
        )

    def session(self) -> LocalTrellisSession:
        return LocalTrellisSession(self)

    def generate_many(
        self, requests: Iterable[AssetGenerationRequest]
    ) -> list[GeneratedAssetResult]:
        requests = list(requests)
        if not requests:
            return []
        with self.session() as session:
            return [session.generate(request) for request in requests]

    def generate(self, request: AssetGenerationRequest) -> GeneratedAssetResult:
        input_path = self._validate(request)
        output_directory = request.output_directory.resolve()
        output_directory.mkdir(parents=True, exist_ok=True)
        output_path = output_directory / "asset.glb"
        if output_path.is_file() and output_path.stat().st_size > 0:
            return GeneratedAssetResult(output_path, self.provider, self.model_id)

        try:
            with tempfile.TemporaryDirectory(prefix="trellis-runtime-") as cache_root:
                completed = self.run_command(
                    [self.python_executable, str(self.worker_path)],
                    input=json.dumps(self._payload(input_path, output_path)),
                    text=True,
                    capture_output=True,
                    timeout=self.timeout_seconds,
                    check=False,
                    env=self._environment(Path(cache_root)),
                    cwd=str(self.repo_dir),
                )
        except subprocess.TimeoutExpired as error:
            raise TimeoutError(
                f"Local TRELLIS generation exceeded {self.timeout_seconds:g} seconds"
            ) from error
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "unknown worker error").strip()
            raise RuntimeError(f"Local TRELLIS generation failed: {detail}")
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError("Local TRELLIS worker completed without a non-empty GLB")
        return GeneratedAssetResult(output_path, self.provider, self.model_id)


class LocalTrellisSession:
    """Explicit TRELLIS session that reuses one loaded pipeline."""

    def __init__(self, provider: LocalTrellisProvider) -> None:
        self.provider = provider
        self.worker = LocalWorkerSession(
            [provider.python_executable, str(provider.worker_path), "--serve"],
            provider._model_config(),
            startup_timeout_seconds=provider.timeout_seconds,
            generation_timeout_seconds=provider.timeout_seconds,
            environment_factory=provider._environment,
            cwd=provider.repo_dir,
            temporary_prefix="trellis-session-",
        )

    def __enter__(self) -> Self:
        if not (self.provider.repo_dir / "trellis").is_dir():
            raise FileNotFoundError(
                f"TRELLIS source is not initialized under: {self.provider.repo_dir}"
            )
        self.worker.start()
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.worker.close()

    def generate(self, request: AssetGenerationRequest) -> GeneratedAssetResult:
        input_path = self.provider._validate(request)
        output_directory = request.output_directory.resolve()
        output_directory.mkdir(parents=True, exist_ok=True)
        output_path = output_directory / "asset.glb"
        if output_path.is_file() and output_path.stat().st_size > 0:
            return GeneratedAssetResult(output_path, self.provider.provider, self.provider.model_id)
        self.worker.request(
            self.provider._job_payload(input_path, output_path), job_id=request.asset_id
        )
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError("Local TRELLIS worker completed without a non-empty GLB")
        return GeneratedAssetResult(output_path, self.provider.provider, self.provider.model_id)
