from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import bpy

from blender_runtime.structure_contract import StructureContract

ROLE_COLLECTIONS = {
    "structure": "STRUCTURE",
    "task": "TASK",
    "context": "ASSETS",
    "decoration": "ASSETS",
}

class BuildContext:
    """Thin semantic contract around unrestricted agent-authored bpy code."""

    def __init__(self, workspace: Path, scene_spec: dict):
        self.workspace = workspace.resolve()
        self.scene_spec = scene_spec
        self.registry: dict[str, object] = {}
        self.review_checks: list[dict] = []
        floorplan = scene_spec.get("floorplan", {})
        self.structure = StructureContract(scene_spec["id"], floorplan.get("status", "unspecified"))

    @staticmethod
    def _move_to_collection(obj, collection_name: str) -> None:
        target = bpy.data.collections[collection_name]
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)
        target.objects.link(obj)

    def register(
        self,
        obj,
        semantic_id: str,
        role: str = "context",
        members: Iterable | None = None,
    ) -> None:
        """Register one semantic root and optionally its Blender child objects."""
        if semantic_id in self.registry:
            raise ValueError(f"Duplicate semantic ID: {semantic_id}")
        if role not in ROLE_COLLECTIONS:
            raise ValueError(f"Unsupported semantic role: {role}")

        obj["semantic_id"] = semantic_id
        obj["semantic_role"] = role
        self._move_to_collection(obj, ROLE_COLLECTIONS[role])
        for member in members or ():
            if member == obj:
                continue
            member["semantic_owner"] = semantic_id
            member["semantic_role"] = role
            self._move_to_collection(member, ROLE_COLLECTIONS[role])
        self.registry[semantic_id] = obj

    def register_room(
        self,
        room_id: str,
        floor_polygon,
        height: float,
        floor_z: float = 0.0,
        source: str | None = None,
    ) -> None:
        """Record resolved room geometry for downstream room agents."""
        self.structure.register_room(room_id, floor_polygon, height, floor_z, source)

    def register_wall(
        self,
        wall_id: str,
        start,
        end,
        thickness: float,
        height: float,
        adjacent_rooms=(),
    ) -> None:
        """Record a shared wall once instead of duplicating it per room."""
        self.structure.register_wall(
            wall_id,
            start,
            end,
            thickness,
            height,
            adjacent_rooms,
        )

    def register_opening(
        self,
        opening_id: str,
        connects,
        center,
        width: float,
        height: float,
        wall_id: str | None = None,
    ) -> None:
        self.structure.register_opening(
            opening_id,
            connects,
            center,
            width,
            height,
            wall_id,
        )

    def structure_contract(self) -> dict:
        return self.structure.to_dict()

    def add_review_check(
        self,
        check_id: str,
        passed: bool,
        *,
        entity_id: str,
        measured: float,
        required: float,
        units: str = "m",
    ) -> None:
        """Record a scene-specific, machine-readable task-usability check."""
        self.review_checks.append(
            {
                "id": check_id,
                "passed": bool(passed),
                "entity_id": entity_id,
                "measured": measured,
                "required": required,
                "units": units,
            }
        )
