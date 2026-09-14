"""Optional provider boundaries for generated scene assets and backgrounds."""

from .fal import FalImageEditor
from .image_editing import CleanPlateRequest, CleanPlateResult, ImageEditingProvider
from .worldlabs import StaticBackgroundRequest, StaticBackgroundResult, WorldLabsProvider

__all__ = [
    "CleanPlateRequest",
    "CleanPlateResult",
    "FalImageEditor",
    "ImageEditingProvider",
    "StaticBackgroundRequest",
    "StaticBackgroundResult",
    "WorldLabsProvider",
]
