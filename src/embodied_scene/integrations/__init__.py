"""Optional provider boundaries for generated scene assets and backgrounds."""

from .fal import FalImageEditor, FalImageGenerator
from .generation_3d import (
    AssetGenerationRequest,
    GeneratedAssetResult,
    Hunyuan3DProvider,
    latest_asset_reference,
    select_asset_iteration,
)
from .image_editing import (
    CleanPlateRequest,
    CleanPlateResult,
    ImageEditingProvider,
    ImageEditRequest,
    ImageEditResult,
    ImageGenerationProvider,
    ImageGenerationRequest,
    ImageGenerationResult,
)
from .local_sd35 import LocalSD35ImageGenerator, LocalSD35Session
from .local_trellis import LocalTrellisProvider, LocalTrellisSession
from .worldlabs import StaticBackgroundRequest, StaticBackgroundResult, WorldLabsProvider

__all__ = [
    "AssetGenerationRequest",
    "CleanPlateRequest",
    "CleanPlateResult",
    "FalImageEditor",
    "FalImageGenerator",
    "GeneratedAssetResult",
    "Hunyuan3DProvider",
    "ImageEditRequest",
    "ImageEditResult",
    "ImageEditingProvider",
    "ImageGenerationProvider",
    "ImageGenerationRequest",
    "ImageGenerationResult",
    "LocalSD35ImageGenerator",
    "LocalSD35Session",
    "LocalTrellisProvider",
    "LocalTrellisSession",
    "StaticBackgroundRequest",
    "StaticBackgroundResult",
    "WorldLabsProvider",
    "latest_asset_reference",
    "select_asset_iteration",
]
