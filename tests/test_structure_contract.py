from pathlib import Path

import pytest
import yaml

from blender_runtime.structure_contract import StructureContract
from embodied_scene.specs import validate_specification


def test_irregular_room_and_shared_wall_are_exported(tmp_path: Path) -> None:
    contract = StructureContract("home", source_status="draft")
    contract.register_room(
        "living_room",
        [(0, 0), (5, 0), (5, 2), (3, 2), (3, 4), (0, 4)],
        height=2.7,
    )
    contract.register_wall(
        "wall_living_east",
        (5, 0),
        (5, 2),
        thickness=0.2,
        height=2.7,
        adjacent_rooms=["living_room"],
    )
    contract.register_opening(
        "door_living",
        connects=["living_room"],
        center=(5, 1, 1.05),
        width=0.9,
        height=2.1,
        wall_id="wall_living_east",
    )
    result = contract.to_dict()
    assert result["status"] == "resolved"
    assert len(result["rooms"]["living_room"]["floor_polygon"]) == 6
    assert result["openings"]["door_living"]["wall_id"] == "wall_living_east"
    path = tmp_path / "structure_contract.json"
    path.write_text(yaml.safe_dump(result), encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    validate_specification(path, "structure-contract.schema.json", root=root)


def test_structure_contract_rejects_unknown_opening_wall() -> None:
    contract = StructureContract("home")
    contract.register_room("room", [(0, 0), (1, 0), (1, 1)], height=2.7)
    contract.register_opening(
        "door",
        connects=["room"],
        center=(1, 0.5, 1),
        width=0.8,
        height=2,
        wall_id="missing_wall",
    )
    with pytest.raises(ValueError, match="unknown wall"):
        contract.to_dict()


def test_structure_contract_rejects_self_intersecting_room() -> None:
    contract = StructureContract("home")
    with pytest.raises(ValueError, match="self-intersecting"):
        contract.register_room(
            "room",
            [(0, 0), (2, 2), (0, 2), (2, 0), (3, 1)],
            height=2.7,
        )
