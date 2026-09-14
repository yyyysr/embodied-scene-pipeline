from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class CleanPlateRequest:
    source_image: Path
    prompt: str
    output_directory: Path
    mask_image: Path | None = None


@dataclass(frozen=True)
class CleanPlateResult:
    image_path: Path
    provider: str
    model: str


class ImageEditingProvider(Protocol):
    def create_clean_plate(self, request: CleanPlateRequest) -> CleanPlateResult: ...


def validate_image_input(path: Path) -> Path:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Image does not exist: {path}")
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValueError(f"Unsupported image type: {path.suffix}")
    if path.stat().st_size == 0:
        raise ValueError(f"Image is empty: {path}")
    return path
