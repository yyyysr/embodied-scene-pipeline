from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from .fal_queue import FalQueueClient, file_data_uri
from .http import HttpTransport, UrllibTransport
from .image_editing import (
    CleanPlateRequest,
    CleanPlateResult,
    ImageEditRequest,
    ImageEditResult,
    ImageGenerationRequest,
    ImageGenerationResult,
    validate_image_input,
)

FAL_EDIT_ENDPOINTS = {
    "nano-banana": "fal-ai/nano-banana-2/edit",
    "gpt-image-2": "openai/gpt-image-2/edit",
}

FAL_IMAGE_ENDPOINTS = {
    "nano-banana": "fal-ai/nano-banana-2",
    "gpt-image-2": "openai/gpt-image-2",
}


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

    def _input(self, request: ImageEditRequest) -> dict:
        source = validate_image_input(request.source_image)
        payload = {
            "prompt": request.prompt,
            "image_urls": [file_data_uri(source)],
            "num_images": 1,
            "output_format": "png",
        }
        if self.provider == "nano-banana":
            payload.update({"aspect_ratio": "auto", "resolution": "1K", "limit_generations": True})
        else:
            payload.update({"image_size": "auto", "quality": "medium"})
            if request.mask_image:
                payload["mask_image_url"] = file_data_uri(validate_image_input(request.mask_image))
        return payload

    def edit(self, request: ImageEditRequest) -> ImageEditResult:
        if not request.prompt.strip():
            raise ValueError("Image-edit prompt must not be empty")
        if Path(request.output_filename).name != request.output_filename:
            raise ValueError("Image-edit output_filename must be a file name")
        if Path(request.state_filename).name != request.state_filename:
            raise ValueError("Image-edit state_filename must be a file name")
        output_directory = request.output_directory.resolve()
        output_directory.mkdir(parents=True, exist_ok=True)
        output_path = output_directory / request.output_filename
        state_path = output_directory / request.state_filename
        if not state_path.exists() and output_path.is_file() and output_path.stat().st_size > 0:
            return ImageEditResult(output_path, "fal", self.provider)
        queue = FalQueueClient(
            api_key=self.api_key,
            transport=self.transport,
            poll_interval_seconds=self.poll_interval_seconds,
            timeout_seconds=self.timeout_seconds,
            sleep=self.sleep,
            clock=self.clock,
        )
        result = queue.run(self.endpoint, self._input(request), state_path)
        image_url = _first_image_url(result.data)
        if not image_url:
            raise RuntimeError("FAL image edit completed without an image URL")
        self.transport.download(image_url, output_path)
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError("FAL clean-plate download is missing or empty")
        state_path.unlink(missing_ok=True)
        return ImageEditResult(output_path, "fal", self.provider)

    def create_clean_plate(self, request: CleanPlateRequest) -> CleanPlateResult:
        return self.edit(request)


class FalImageGenerator:
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
        if provider not in FAL_IMAGE_ENDPOINTS:
            raise ValueError(f"Unsupported FAL image generator: {provider}")
        self.provider = provider
        self.endpoint = FAL_IMAGE_ENDPOINTS[provider]
        self.api_key = api_key
        self.transport = transport or UrllibTransport()
        self.poll_interval_seconds = poll_interval_seconds
        self.timeout_seconds = timeout_seconds
        self.sleep = sleep
        self.clock = clock

    def _input(self, request: ImageGenerationRequest) -> dict:
        payload = {
            "prompt": request.prompt,
            "num_images": 1,
            "output_format": "png",
        }
        if self.provider == "nano-banana":
            payload.update(
                {
                    "aspect_ratio": "1:1",
                    "resolution": "1K",
                    "limit_generations": True,
                    "enable_web_search": False,
                }
            )
        else:
            payload.update(
                {
                    "image_size": "square_hd",
                    "background": "opaque",
                    "quality": "medium",
                }
            )
        return payload

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        if not request.prompt.strip():
            raise ValueError("Image-generation prompt must not be empty")
        if Path(request.output_filename).name != request.output_filename:
            raise ValueError("Image-generation output_filename must be a file name")
        if Path(request.state_filename).name != request.state_filename:
            raise ValueError("Image-generation state_filename must be a file name")
        output_directory = request.output_directory.resolve()
        output_directory.mkdir(parents=True, exist_ok=True)
        output_path = output_directory / request.output_filename
        state_path = output_directory / request.state_filename
        if not state_path.exists() and output_path.is_file() and output_path.stat().st_size > 0:
            return ImageGenerationResult(output_path, "fal", self.provider)
        queue = FalQueueClient(
            api_key=self.api_key,
            transport=self.transport,
            poll_interval_seconds=self.poll_interval_seconds,
            timeout_seconds=self.timeout_seconds,
            sleep=self.sleep,
            clock=self.clock,
        )
        result = queue.run(self.endpoint, self._input(request), state_path)
        image_url = _first_image_url(result.data)
        if not image_url:
            raise RuntimeError("FAL image generation completed without an image URL")
        self.transport.download(image_url, output_path)
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError("FAL reference-image download is missing or empty")
        state_path.unlink(missing_ok=True)
        return ImageGenerationResult(output_path, "fal", self.provider)
