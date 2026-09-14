from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .fal_queue import FalQueueClient, file_data_uri
from .http import HttpTransport, UrllibTransport
from .image_editing import validate_image_input

GenerateType = Literal["Normal", "LowPoly", "Geometry"]
PolygonType = Literal["triangle", "quadrilateral"]
AssetGenerationMode = Literal["text-to-3d", "image-to-3d"]

HUNYUAN_3D_ENDPOINTS = {
    "text-to-3d": "fal-ai/hunyuan3d-v3/text-to-3d",
    "image-to-3d": "fal-ai/hunyuan3d-v3/image-to-3d",
}
MIN_FACE_COUNT = 40_000
MAX_FACE_COUNT = 1_500_000


def _validate_asset_id(asset_id: str) -> None:
    if not re.fullmatch(r"[a-z0-9_]+", asset_id):
        raise ValueError("asset_id must contain lowercase letters, digits, or underscores")


def _asset_iterations(mesh_root: Path, asset_id: str) -> list[tuple[int, Path]]:
    _validate_asset_id(asset_id)
    asset_root = mesh_root / asset_id
    asset_root.mkdir(parents=True, exist_ok=True)
    iterations = []
    for candidate in asset_root.glob("iteration_*"):
        try:
            index = int(candidate.name.removeprefix("iteration_"))
        except ValueError:
            continue
        if candidate.is_dir():
            iterations.append((index, candidate))
    return sorted(iterations)


def select_asset_iteration(mesh_root: Path, asset_id: str, *, regenerate: bool = False) -> Path:
    """Reuse existing work unless a completed candidate is explicitly regenerated."""
    iterations = _asset_iterations(mesh_root, asset_id)
    if iterations:
        index, latest = iterations[-1]
        asset = latest / "asset.glb"
        completed = asset.is_file() and asset.stat().st_size > 0
        if not regenerate or not completed:
            return latest
        next_index = index + 1
    else:
        next_index = 1
    destination = mesh_root / asset_id / f"iteration_{next_index:03d}"
    destination.mkdir()
    return destination


def latest_asset_reference(mesh_root: Path, asset_id: str) -> Path | None:
    for _, iteration in reversed(_asset_iterations(mesh_root, asset_id)):
        reference = iteration / "reference.png"
        if reference.is_file() and reference.stat().st_size > 0:
            return reference
    return None


@dataclass(frozen=True)
class AssetGenerationRequest:
    asset_id: str
    prompt: str
    target_dimensions: tuple[float, float, float]
    reference_images: tuple[Path, ...]
    output_directory: Path
    mode: AssetGenerationMode = "image-to-3d"
    face_count: int = 50_000
    enable_pbr: bool = True
    generate_type: GenerateType = "Normal"
    polygon_type: PolygonType = "triangle"


@dataclass(frozen=True)
class GeneratedAssetResult:
    asset_path: Path
    provider: str
    model: str


def _model_url(value: dict) -> str | None:
    preferred = value.get("model_glb")
    if isinstance(preferred, dict) and isinstance(preferred.get("url"), str):
        return preferred["url"]
    for key, child in value.items():
        if isinstance(child, dict):
            url = child.get("url")
            content_type = str(child.get("content_type", ""))
            if isinstance(url, str) and (
                content_type == "model/gltf-binary" or key.endswith("glb")
            ):
                return url
            if found := _model_url(child):
                return found
    return None


class Hunyuan3DProvider:
    model = "hunyuan3d-v3"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        transport: HttpTransport | None = None,
        poll_interval_seconds: float = 10.0,
        timeout_seconds: float = 1800.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        text_endpoint: str = HUNYUAN_3D_ENDPOINTS["text-to-3d"],
        image_endpoint: str = HUNYUAN_3D_ENDPOINTS["image-to-3d"],
    ):
        self.api_key = api_key
        self.transport = transport or UrllibTransport()
        self.poll_interval_seconds = poll_interval_seconds
        self.timeout_seconds = timeout_seconds
        self.sleep = sleep
        self.clock = clock
        self.endpoints = {
            "text-to-3d": text_endpoint,
            "image-to-3d": image_endpoint,
        }

    @staticmethod
    def _validate(request: AssetGenerationRequest) -> Path | None:
        _validate_asset_id(request.asset_id)
        if not request.prompt.strip():
            raise ValueError("Asset prompt must not be empty")
        if len(request.target_dimensions) != 3 or any(
            value <= 0 for value in request.target_dimensions
        ):
            raise ValueError("target_dimensions must contain three positive meter values")
        if request.mode not in HUNYUAN_3D_ENDPOINTS:
            raise ValueError("mode must be text-to-3d or image-to-3d")
        if request.mode == "image-to-3d" and not request.reference_images:
            raise ValueError("Hunyuan image-to-3d requires one isolated reference image")
        if not MIN_FACE_COUNT <= request.face_count <= MAX_FACE_COUNT:
            raise ValueError(f"face_count must be between {MIN_FACE_COUNT} and {MAX_FACE_COUNT}")
        if request.generate_type not in {"Normal", "LowPoly", "Geometry"}:
            raise ValueError("generate_type must be Normal, LowPoly, or Geometry")
        if request.polygon_type not in {"triangle", "quadrilateral"}:
            raise ValueError("polygon_type must be triangle or quadrilateral")
        if request.mode == "image-to-3d":
            return validate_image_input(request.reference_images[0])
        return None

    def generate(self, request: AssetGenerationRequest) -> GeneratedAssetResult:
        source_image = self._validate(request)
        endpoint = self.endpoints[request.mode]
        output_directory = request.output_directory.resolve()
        output_directory.mkdir(parents=True, exist_ok=True)
        output_path = output_directory / "asset.glb"
        state_path = output_directory / ".asset.request.json"
        if not state_path.exists() and output_path.is_file() and output_path.stat().st_size > 0:
            return GeneratedAssetResult(output_path, "fal", self.model)

        payload = {
            "generate_type": request.generate_type,
            "enable_pbr": request.enable_pbr,
            "face_count": request.face_count,
        }
        if source_image is None:
            payload["prompt"] = request.prompt
        else:
            payload["input_image_url"] = file_data_uri(source_image)
        if request.generate_type == "LowPoly":
            payload["polygon_type"] = request.polygon_type
        queue = FalQueueClient(
            api_key=self.api_key,
            transport=self.transport,
            poll_interval_seconds=self.poll_interval_seconds,
            timeout_seconds=self.timeout_seconds,
            sleep=self.sleep,
            clock=self.clock,
        )
        result = queue.run(endpoint, payload, state_path)
        url = _model_url(result.data)
        if not url:
            raise RuntimeError("Hunyuan3D completed without a GLB model URL")
        self.transport.download(url, output_path)
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError("Hunyuan3D GLB download is missing or empty")
        state_path.unlink(missing_ok=True)
        return GeneratedAssetResult(output_path, "fal", self.model)


def generate_asset(request: AssetGenerationRequest) -> Path:
    """Generate one candidate GLB; normalization remains a separate Blender step."""
    return Hunyuan3DProvider().generate(request).asset_path
