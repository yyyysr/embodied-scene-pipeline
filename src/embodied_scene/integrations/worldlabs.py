from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StaticBackgroundRequest:
    prompt: str
    reference_images: tuple[Path, ...]
    output_directory: Path


def generate_static_background(request: StaticBackgroundRequest) -> Path:
    raise NotImplementedError("Configure a World Labs adapter in a later milestone")

