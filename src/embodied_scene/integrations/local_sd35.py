from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Self

from ._local_worker import LocalWorkerSession
from .image_editing import ImageGenerationRequest, ImageGenerationResult


def _default_worker_path() -> Path:
    return Path(__file__).resolve().parents[3] / "local_runtime" / "sd35_worker.py"


class LocalSD35ImageGenerator:
    """Generate one reference image through an isolated local SD3.5 worker."""

    provider = "local"

    def __init__(
        self,
        *,
        python_executable: str | None = None,
        worker_path: Path | None = None,
        model_id: str = "stabilityai/stable-diffusion-3.5-medium",
        device: str = "cuda",
        dtype: str = "float16",
        width: int = 1024,
        height: int = 1024,
        num_inference_steps: int = 25,
        guidance_scale: float = 7.0,
        seed: int = 42,
        negative_prompt: str | None = None,
        enable_model_cpu_offload: bool = True,
        enable_xformers: bool = False,
        enable_attention_slicing: bool = True,
        local_files_only: bool = False,
        timeout_seconds: float = 900.0,
        run_command: Callable[..., Any] = subprocess.run,
    ):
        self.python_executable = (
            os.environ.get("EMBODIED_SCENE_LOCAL_ASSET_PYTHON")
            or python_executable
            or sys.executable
        )
        self.worker_path = (worker_path or _default_worker_path()).resolve()
        self.model_id = model_id
        self.device = device
        self.dtype = dtype
        self.width = width
        self.height = height
        self.num_inference_steps = num_inference_steps
        self.guidance_scale = guidance_scale
        self.seed = seed
        self.negative_prompt = negative_prompt
        self.enable_model_cpu_offload = enable_model_cpu_offload
        self.enable_xformers = enable_xformers
        self.enable_attention_slicing = enable_attention_slicing
        self.local_files_only = local_files_only
        self.timeout_seconds = timeout_seconds
        self.run_command = run_command

    def _model_config(self) -> dict:
        return {
            "model_id": self.model_id,
            "device": self.device,
            "dtype": self.dtype,
            "enable_model_cpu_offload": self.enable_model_cpu_offload,
            "enable_xformers": self.enable_xformers,
            "enable_attention_slicing": self.enable_attention_slicing,
            "local_files_only": self.local_files_only,
        }

    def _job_payload(self, request: ImageGenerationRequest, output_path: Path) -> dict:
        return {
            "prompt": request.prompt,
            "negative_prompt": self.negative_prompt,
            "output_path": str(output_path),
            "width": self.width,
            "height": self.height,
            "num_inference_steps": self.num_inference_steps,
            "guidance_scale": self.guidance_scale,
            "seed": self.seed,
        }

    def _payload(self, request: ImageGenerationRequest, output_path: Path) -> dict:
        return self._model_config() | self._job_payload(request, output_path)

    def _output_path(self, request: ImageGenerationRequest) -> Path:
        if not request.prompt.strip():
            raise ValueError("Image-generation prompt must not be empty")
        if Path(request.output_filename).name != request.output_filename:
            raise ValueError("Image-generation output_filename must be a file name")
        if Path(request.output_filename).suffix.lower() != ".png":
            raise ValueError("Local SD3.5 output_filename must end with .png")
        if not self.worker_path.is_file():
            raise FileNotFoundError(f"SD3.5 worker does not exist: {self.worker_path}")
        output_directory = request.output_directory.resolve()
        output_directory.mkdir(parents=True, exist_ok=True)
        return output_directory / request.output_filename

    def session(self) -> LocalSD35Session:
        return LocalSD35Session(self)

    def generate_many(
        self, requests: Iterable[ImageGenerationRequest]
    ) -> list[ImageGenerationResult]:
        requests = list(requests)
        if not requests:
            return []
        with self.session() as session:
            return [session.generate(request) for request in requests]

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        output_path = self._output_path(request)
        if output_path.is_file() and output_path.stat().st_size > 0:
            return ImageGenerationResult(output_path, self.provider, self.model_id)

        try:
            completed = self.run_command(
                [self.python_executable, str(self.worker_path)],
                input=json.dumps(self._payload(request, output_path)),
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise TimeoutError(
                f"Local SD3.5 generation exceeded {self.timeout_seconds:g} seconds"
            ) from error
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "unknown worker error").strip()
            raise RuntimeError(f"Local SD3.5 generation failed: {detail}")
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError("Local SD3.5 worker completed without a non-empty image")
        return ImageGenerationResult(output_path, self.provider, self.model_id)


class LocalSD35Session:
    """Explicit SD3.5 session that reuses one loaded pipeline."""

    def __init__(self, generator: LocalSD35ImageGenerator) -> None:
        self.generator = generator
        self.worker = LocalWorkerSession(
            [generator.python_executable, str(generator.worker_path), "--serve"],
            generator._model_config(),
            startup_timeout_seconds=generator.timeout_seconds,
            generation_timeout_seconds=generator.timeout_seconds,
            temporary_prefix="sd35-session-",
        )

    def __enter__(self) -> Self:
        self.worker.start()
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.worker.close()

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        output_path = self.generator._output_path(request)
        if output_path.is_file() and output_path.stat().st_size > 0:
            return ImageGenerationResult(
                output_path, self.generator.provider, self.generator.model_id
            )
        self.worker.request(self.generator._job_payload(request, output_path))
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError("Local SD3.5 worker completed without a non-empty image")
        return ImageGenerationResult(output_path, self.generator.provider, self.generator.model_id)
