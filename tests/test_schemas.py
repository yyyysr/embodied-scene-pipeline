from pathlib import Path

import pytest
import yaml
from jsonschema import ValidationError

from embodied_scene.specs import validate_specification


def test_tabletop_example_is_valid() -> None:
    root = Path(__file__).resolve().parents[1]
    example = root / "examples" / "tabletop_pick_and_place"
    task = validate_specification(example / "task.yaml", "task.schema.json", root=root)
    scene = validate_specification(example / "scene.yaml", "scene.schema.json", root=root)
    assert task["id"] == scene["id"]


def _validate_scene(tmp_path: Path, data: dict) -> dict:
    root = Path(__file__).resolve().parents[1]
    path = tmp_path / "scene.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return validate_specification(path, "scene.schema.json", root=root)


def test_scripted_scene_accepts_draft_rooms_and_semantic_assets(tmp_path: Path) -> None:
    scene = {
        "id": "irregular_home",
        "environment": "home",
        "implementation": {
            "mode": "blender_script",
            "script": "source/build_scene.py",
            "entrypoint": "build_scene",
        },
        "floorplan": {
            "status": "draft",
            "source_reference": "input/references/floorplan.png",
            "scale": {"status": "inferred", "meters_per_pixel": 0.0092},
            "origin_pixel": [410, 1024],
        },
        "rooms": [{"id": "living_room", "purpose": "living"}],
        "objects": [{"id": "living_room_sofa", "role": "context"}],
    }
    assert _validate_scene(tmp_path, scene)["floorplan"]["status"] == "draft"


def test_resolved_room_requires_polygon_and_height(tmp_path: Path) -> None:
    scene = {
        "id": "invalid_home",
        "environment": "home",
        "implementation": {
            "mode": "blender_script",
            "script": "source/build_scene.py",
            "entrypoint": "build_scene",
        },
        "rooms": [{"id": "living_room", "status": "resolved"}],
        "objects": [],
    }
    with pytest.raises(ValidationError):
        _validate_scene(tmp_path, scene)


def test_primitive_scene_still_requires_primitive_geometry(tmp_path: Path) -> None:
    scene = {
        "id": "invalid_tabletop",
        "environment": "tabletop",
        "objects": [{"id": "cup", "role": "task"}],
    }
    with pytest.raises(ValidationError):
        _validate_scene(tmp_path, scene)


def test_3dgs_scene_records_only_accepted_local_result_paths(tmp_path: Path) -> None:
    scene = {
        "id": "tabletop_context",
        "environment": "tabletop",
        "world": {
            "background_intent": "auto",
            "background_mode": "3dgs",
            "background_decision": "use_clean_plate",
            "background_input": ("generated_assets/backgrounds/iteration_001/clean_plate.png"),
            "background_asset": ("generated_assets/backgrounds/iteration_001/world_full_res.spz"),
        },
        "objects": [],
    }
    assert _validate_scene(tmp_path, scene)["world"]["background_mode"] == "3dgs"


def test_3dgs_scene_requires_input_and_local_spz(tmp_path: Path) -> None:
    scene = {
        "id": "invalid_background",
        "environment": "tabletop",
        "world": {
            "background_mode": "3dgs",
            "background_decision": "use_reference_directly",
        },
        "objects": [],
    }
    with pytest.raises(ValidationError):
        _validate_scene(tmp_path, scene)


def test_generated_asset_requires_accepted_local_glb(tmp_path: Path) -> None:
    valid = {
        "id": "generated_scene",
        "environment": "tabletop",
        "objects": [
            {
                "id": "ceramic_mug",
                "role": "context",
                "modeling_method": "generated_3d",
                "source_file": (
                    "generated_assets/meshes/ceramic_mug/iteration_001/asset.glb"
                ),
            }
        ],
        "implementation": {
            "mode": "blender_script",
            "script": "source/build_scene.py",
            "entrypoint": "build_scene",
        },
    }
    assert _validate_scene(tmp_path, valid)["objects"][0]["source_file"].endswith("asset.glb")
    del valid["objects"][0]["source_file"]
    with pytest.raises(ValidationError):
        _validate_scene(tmp_path, valid)
