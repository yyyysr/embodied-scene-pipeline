from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

BackgroundIntent = Literal["none", "auto", "required"]
BackgroundContent = Literal["blank", "task_only", "simple", "rich_static"]
BackgroundMode = Literal["none", "blender", "3dgs"]


@dataclass(frozen=True)
class BackgroundDecision:
    mode: BackgroundMode
    reason: str
    clean_plate_required: bool = False


def decide_tabletop_background(
    *,
    intent: BackgroundIntent,
    has_reference_image: bool,
    content: BackgroundContent,
    contains_excluded_entities: bool = False,
    cleanup_feasible: bool = True,
) -> BackgroundDecision:
    """Resolve an agent's semantic image assessment into a reproducible action.

    Image understanding remains an agent responsibility. This function encodes the
    routing policy after the agent classifies the evidence; it does not pretend to
    infer image content with brittle pixel heuristics.
    """
    if intent == "none":
        return BackgroundDecision("none", "user_requested_no_background")
    if not has_reference_image:
        if intent == "required":
            return BackgroundDecision("none", "required_background_needs_reference")
        return BackgroundDecision("blender", "no_reference_or_background_request")
    if content == "blank":
        return BackgroundDecision("blender", "blank_background")
    if content == "task_only":
        return BackgroundDecision("blender", "reference_contains_task_region_only")
    if content == "simple" and intent != "required":
        return BackgroundDecision("blender", "simple_blender_equivalent")
    if contains_excluded_entities and not cleanup_feasible:
        return BackgroundDecision("blender", "clean_plate_would_require_large_hallucination")
    return BackgroundDecision(
        "3dgs",
        "use_clean_plate" if contains_excluded_entities else "use_reference_directly",
        clean_plate_required=contains_excluded_entities,
    )


def next_background_iteration(background_root: Path) -> Path:
    """Create the next non-overwriting background output directory."""
    background_root.mkdir(parents=True, exist_ok=True)
    indices = []
    for candidate in background_root.glob("iteration_*"):
        try:
            indices.append(int(candidate.name.removeprefix("iteration_")))
        except ValueError:
            continue
    destination = background_root / f"iteration_{max(indices, default=0) + 1:03d}"
    destination.mkdir()
    return destination
