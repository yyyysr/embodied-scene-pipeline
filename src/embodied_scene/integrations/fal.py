from __future__ import annotations

import base64
import mimetypes
import os
import time
from collections.abc import Callable

from .http import HttpTransport, UrllibTransport
from .image_editing import CleanPlateRequest, CleanPlateResult, validate_image_input
from .state import read_state, write_state

FAL_EDIT_ENDPOINTS = {
    "nano-banana": "fal-ai/nano-banana-2/edit",
    "gpt-image-2": "openai/gpt-image-2/edit",
}


def _data_uri(path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _first_image_url(value) -> str | None:
    if isinstance(value, dict):
        images = value.get("images")
        if isinstance(images, list):
            for image in images:
                if isinstance(image, dict) and isinstance(image.get("url"), str):
                    return image["url"]
        if isinstance(value.get("url"), str):
            return value["url"]
        for child in value.values():
            if found := _first_image_url(child):
                return found
    elif isinstance(value, list):
        for child in value:
            if found := _first_image_url(child):
                return found
    return None


class FalImageEditor:
    def __init__(
        self,
        *,
        provider: str = "nano-banana",
        api_key: str | None = None,
        transport: HttpTransport | None = None,
        poll_interval_seconds: float = 5.0,
        timeout_seconds: float = 900.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        if provider not in FAL_EDIT_ENDPOINTS:
            raise ValueError(f"Unsupported FAL image editor: {provider}")
        self.provider = provider
        self.endpoint = FAL_EDIT_ENDPOINTS[provider]
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

    def _input(self, request: CleanPlateRequest) -> dict:
        source = validate_image_input(request.source_image)
        payload = {
            "prompt": request.prompt,
            "image_urls": [_data_uri(source)],
            "num_images": 1,
            "output_format": "png",
        }
        if self.provider == "nano-banana":
            payload.update({"aspect_ratio": "auto", "resolution": "1K", "limit_generations": True})
        else:
            payload.update({"image_size": "auto", "quality": "medium"})
            if request.mask_image:
                payload["mask_image_url"] = _data_uri(validate_image_input(request.mask_image))
        return payload

    def create_clean_plate(self, request: CleanPlateRequest) -> CleanPlateResult:
        if not request.prompt.strip():
            raise ValueError("Clean-plate prompt must not be empty")
        output_directory = request.output_directory.resolve()
        output_directory.mkdir(parents=True, exist_ok=True)
        output_path = output_directory / "clean_plate.png"
        state_path = output_directory / ".clean_plate.request.json"
        state = read_state(state_path)
        if state is None and output_path.is_file() and output_path.stat().st_size > 0:
            return CleanPlateResult(output_path, "fal", self.provider)

        if state:
            if state.get("endpoint") != self.endpoint or not state.get("request_id"):
                raise ValueError(f"Invalid resumable FAL state: {state_path}")
        else:
            submitted = self.transport.request_json(
                "POST",
                f"https://queue.fal.run/{self.endpoint}",
                headers=self.headers,
                payload=self._input(request),
            )
            request_id = submitted.get("request_id")
            if not request_id:
                raise RuntimeError("FAL submit response did not include request_id")
            state = {
                "provider": "fal",
                "endpoint": self.endpoint,
                "request_id": request_id,
                "status_url": submitted.get("status_url"),
                "response_url": submitted.get("response_url"),
                "status": "submitted",
            }
            write_state(state_path, state)

        request_id = str(state["request_id"])
        status_url = state.get("status_url") or (
            f"https://queue.fal.run/{self.endpoint}/requests/{request_id}/status"
        )
        deadline = self.clock() + self.timeout_seconds
        while True:
            status = self.transport.request_json("GET", status_url, headers=self.headers)
            status_name = str(status.get("status", "UNKNOWN")).upper()
            write_state(state_path, {**state, "status": status_name})
            if status.get("error"):
                raise RuntimeError(f"FAL image edit failed: {status['error']}")
            if status_name == "COMPLETED":
                break
            if status_name in {"FAILED", "CANCELLED", "CANCELED"}:
                raise RuntimeError(f"FAL image edit ended with status {status_name}")
            if self.clock() >= deadline:
                raise TimeoutError(f"FAL image edit timed out; resume state kept at {state_path}")
            self.sleep(self.poll_interval_seconds)

        response_url = state.get("response_url") or (
            f"https://queue.fal.run/{self.endpoint}/requests/{request_id}"
        )
        result = self.transport.request_json("GET", response_url, headers=self.headers)
        image_url = _first_image_url(result)
        if not image_url:
            raise RuntimeError("FAL image edit completed without an image URL")
        self.transport.download(image_url, output_path)
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError("FAL clean-plate download is missing or empty")
        state_path.unlink(missing_ok=True)
        return CleanPlateResult(output_path, "fal", self.provider)
