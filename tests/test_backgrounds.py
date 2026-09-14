import os
from pathlib import Path

from blender_runtime.backgrounds import validate_background
from embodied_scene.backgrounds import decide_tabletop_background, next_background_iteration
from embodied_scene.integrations.environment import load_env_file
from embodied_scene.integrations.generation_3d import (
    latest_asset_reference,
    select_asset_iteration,
)


def test_background_policy_skips_unrequested_semantic_tabletop() -> None:
    decision = decide_tabletop_background(
        intent="auto", has_reference_image=False, content="task_only"
    )
    assert decision.mode == "blender"
    assert decision.reason == "no_reference_or_background_request"


def test_background_policy_requires_clean_plate_for_rich_contaminated_reference() -> None:
    decision = decide_tabletop_background(
        intent="auto",
        has_reference_image=True,
        content="rich_static",
        contains_excluded_entities=True,
    )
    assert decision.mode == "3dgs"
    assert decision.clean_plate_required is True
    assert decision.reason == "use_clean_plate"


def test_background_policy_skips_infeasible_cleanup() -> None:
    decision = decide_tabletop_background(
        intent="required",
        has_reference_image=True,
        content="rich_static",
        contains_excluded_entities=True,
        cleanup_feasible=False,
    )
    assert decision.mode == "blender"
    assert decision.reason == "clean_plate_would_require_large_hallucination"


def test_background_iterations_do_not_overwrite(tmp_path: Path) -> None:
    assert next_background_iteration(tmp_path).name == "iteration_001"
    assert next_background_iteration(tmp_path).name == "iteration_002"


def test_asset_iteration_advances_only_for_explicit_completed_regeneration(
    tmp_path: Path,
) -> None:
    first = select_asset_iteration(tmp_path, "mug")
    assert first.name == "iteration_001"
    assert select_asset_iteration(tmp_path, "mug") == first
    assert select_asset_iteration(tmp_path, "mug", regenerate=True) == first

    (first / "asset.glb").write_bytes(b"candidate")
    assert select_asset_iteration(tmp_path, "mug") == first
    second = select_asset_iteration(tmp_path, "mug", regenerate=True)
    assert second.name == "iteration_002"
    assert select_asset_iteration(tmp_path, "mug", regenerate=True) == second
    assert select_asset_iteration(tmp_path, "chair").name == "iteration_001"


def test_latest_asset_reference_can_be_reused_across_model_iterations(tmp_path: Path) -> None:
    first = select_asset_iteration(tmp_path, "mug")
    reference = first / "reference.png"
    reference.write_bytes(b"reference")
    (first / "asset.glb").write_bytes(b"candidate")
    select_asset_iteration(tmp_path, "mug", regenerate=True)
    assert latest_asset_reference(tmp_path, "mug") == reference


def test_selected_background_files_are_checked(tmp_path: Path) -> None:
    background = tmp_path / "generated_assets" / "backgrounds" / "iteration_001"
    background.mkdir(parents=True)
    (background / "clean_plate.png").write_bytes(b"image")
    (background / "world_full_res.spz").write_bytes(b"splat")
    spec = {
        "world": {
            "background_mode": "3dgs",
            "background_input": ("generated_assets/backgrounds/iteration_001/clean_plate.png"),
            "background_asset": ("generated_assets/backgrounds/iteration_001/world_full_res.spz"),
        }
    }
    checks, findings = validate_background(spec, tmp_path)
    assert all(checks.values())
    assert findings == []


def test_missing_optional_background_is_major_not_blocking(tmp_path: Path) -> None:
    spec = {
        "world": {
            "background_mode": "3dgs",
            "background_input": "input/references/source.png",
            "background_asset": ("generated_assets/backgrounds/iteration_001/world_full_res.spz"),
        }
    }
    checks, findings = validate_background(spec, tmp_path)
    assert checks["background_asset_exists"] is False
    assert {finding["severity"] for finding in findings} == {"major"}


def test_env_file_does_not_override_existing_values(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("FAL_KEY=file-value\nWORLD_LABS_API_KEY='world-value'\n", encoding="utf-8")
    monkeypatch.setenv("FAL_KEY", "process-value")
    monkeypatch.delenv("WORLD_LABS_API_KEY", raising=False)
    load_env_file(env_file)
    assert os.environ["FAL_KEY"] == "process-value"
    assert os.environ["WORLD_LABS_API_KEY"] == "world-value"
