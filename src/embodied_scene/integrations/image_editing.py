from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ImageEditRequest:
    source_image: Path
    prompt: str
    output_directory: Path
    mask_image: Path | None = None
    output_filename: str = "clean_plate.png"
    state_filename: str = ".clean_plate.request.json"


@dataclass(frozen=True)
class ImageEditResult:
    image_path: Path
    provider: str
    model: str


class ImageEditingProvider(Protocol):
    def edit(self, request: ImageEditRequest) -> ImageEditResult: ...


@dataclass(frozen=True)
class ImageGenerationRequest:
    prompt: str
    output_directory: Path
    output_filename: str = "reference.png"
    state_filename: str = ".reference.request.json"


@dataclass(frozen=True)
class ImageGenerationResult:
    image_path: Path
    provider: str
    model: str


class ImageGenerationProvider(Protocol):
    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult: ...


CleanPlateRequest = ImageEditRequest
CleanPlateResult = ImageEditResult


def validate_image_input(path: Path) -> Path:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Image does not exist: {path}")
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValueError(f"Unsupported image type: {path.suffix}")
    if path.stat().st_size == 0:
        raise ValueError(f"Image is empty: {path}")
    return path
