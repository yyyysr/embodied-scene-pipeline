from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AssetGenerationRequest:
    asset_id: str
    prompt: str
    target_dimensions: tuple[float, float, float]
    reference_images: tuple[Path, ...]
    output_directory: Path


def generate_asset(request: AssetGenerationRequest) -> Path:
    raise NotImplementedError("Configure a 3D-generation adapter in a later milestone")

