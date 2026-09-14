from __future__ import annotations

import base64
import mimetypes
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .http import HttpTransport, UrllibTransport
from .image_editing import validate_image_input
from .state import read_state, write_state


@dataclass(frozen=True)
class StaticBackgroundRequest:
    scene_id: str
    prompt: str
    source_image: Path
    output_directory: Path


@dataclass(frozen=True)
class StaticBackgroundResult:
    splats: dict[str, Path]
    collider_mesh: Path | None = None
    panorama: Path | None = None
    thumbnail: Path | None = None

    @property
    def full_resolution_splat(self) -> Path:
        return self.splats["full_res"]


def _safe_key(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_")[:80]


def _image_prompt(path: Path, text_prompt: str) -> dict:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return {
        "type": "image",
        "image_prompt": {
            "source": "data_base64",
            "data_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
            "extension": path.suffix.lstrip(".").lower(),
            "mime_type": mime,
        },
        "text_prompt": text_prompt,
    }


def _operation_id(operation: dict) -> str:
    value = operation.get("operation_id") or operation.get("id") or operation.get("name")
    if not value:
        raise RuntimeError("World Labs response did not include operation_id")
    return str(value).rstrip("/").split("/")[-1]


class WorldLabsProvider:
    endpoint = "https://api.worldlabs.ai/marble/v1"
    model = "marble-1.1"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        transport: HttpTransport | None = None,
        poll_interval_seconds: float = 15.0,
        timeout_seconds: float = 1800.0,
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
        key = self.api_key or os.environ.get("WORLD_LABS_API_KEY")
        if not key:
            raise RuntimeError("WORLD_LABS_API_KEY is not set")
        return {"WLT-Api-Key": key, "Content-Type": "application/json"}

    def generate(self, request: StaticBackgroundRequest) -> StaticBackgroundResult:
        if not request.scene_id or not request.prompt.strip():
            raise ValueError("World generation requires scene_id and prompt")
        source_image = validate_image_input(request.source_image)
        output_directory = request.output_directory.resolve()
        output_directory.mkdir(parents=True, exist_ok=True)
        state_path = output_directory / ".world.request.json"
        existing_full = output_directory / "world_full_res.spz"
        state = read_state(state_path)
        if state is None and existing_full.is_file() and existing_full.stat().st_size > 0:
            return self._existing_result(output_directory)
        if state:
            if state.get("provider") != "world_labs" or not state.get("request_id"):
                raise ValueError(f"Invalid resumable World Labs state: {state_path}")
            operation = {"operation_id": state["request_id"], "done": False}
        else:
            payload = {
                "display_name": request.scene_id,
                "model": self.model,
                "world_prompt": _image_prompt(source_image, request.prompt),
            }
            operation = self.transport.request_json(
                "POST",
                f"{self.endpoint}/worlds:generate",
                headers=self.headers,
                payload=payload,
            )
            request_id = _operation_id(operation)
            state = {
                "provider": "world_labs",
                "request_id": request_id,
                "status": "completed" if operation.get("done") else "submitted",
            }
            write_state(state_path, state)

        request_id = str(state["request_id"])
        deadline = self.clock() + self.timeout_seconds
        while not operation.get("done") and not operation.get("error"):
            operation = self.transport.request_json(
                "GET",
                f"{self.endpoint}/operations/{request_id}",
                headers=self.headers,
            )
            status = (
                "failed"
                if operation.get("error")
                else ("completed" if operation.get("done") else "running")
            )
            write_state(state_path, {**state, "status": status})
            if operation.get("done"):
                break
            if self.clock() >= deadline:
                raise TimeoutError(
                    f"World Labs generation timed out; resume state kept at {state_path}"
                )
            self.sleep(self.poll_interval_seconds)

        if operation.get("error"):
            raise RuntimeError(f"World Labs generation failed: {operation['error']}")
        response = operation.get("response")
        if not isinstance(response, dict):
            raise TypeError("World Labs operation completed without a response object")
        result = self._download_assets(response, output_directory)
        state_path.unlink(missing_ok=True)
        return result

    def _download_assets(self, response: dict, output_directory: Path) -> StaticBackgroundResult:
        assets = response.get("assets") or {}
        splat_urls = (assets.get("splats") or {}).get("spz_urls") or {}
        if not isinstance(splat_urls, dict) or not splat_urls.get("full_res"):
            raise RuntimeError("World Labs response did not include a full_res SPZ")
        splats = {}
        for key, url in splat_urls.items():
            if not isinstance(url, str) or not url:
                continue
            name = "world_full_res.spz" if key == "full_res" else f"world_{_safe_key(key)}.spz"
            splats[str(key)] = self.transport.download(url, output_directory / name)

        collider = self._optional_download(
            (assets.get("mesh") or {}).get("collider_mesh_url"),
            output_directory / "world_collider.glb",
        )
        panorama = self._optional_download(
            (assets.get("imagery") or {}).get("pano_url"),
            output_directory / "world_pano.png",
        )
        thumbnail = self._optional_download(
            assets.get("thumbnail_url"), output_directory / "world_thumbnail.webp"
        )
        return StaticBackgroundResult(splats, collider, panorama, thumbnail)

    def _optional_download(self, url, destination: Path) -> Path | None:
        return self.transport.download(url, destination) if isinstance(url, str) and url else None

    @staticmethod
    def _existing_result(output_directory: Path) -> StaticBackgroundResult:
        splats = {
            path.stem.removeprefix("world_"): path
            for path in output_directory.glob("world_*.spz")
            if path.stat().st_size > 0
        }
        collider = output_directory / "world_collider.glb"
        panorama = output_directory / "world_pano.png"
        thumbnail = output_directory / "world_thumbnail.webp"
        return StaticBackgroundResult(
            splats,
            collider if collider.is_file() else None,
            panorama if panorama.is_file() else None,
            thumbnail if thumbnail.is_file() else None,
        )


def generate_static_background(request: StaticBackgroundRequest) -> Path:
    """Backward-compatible convenience wrapper returning the required SPZ path."""
    return WorldLabsProvider().generate(request).full_resolution_splat
