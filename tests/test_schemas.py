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
