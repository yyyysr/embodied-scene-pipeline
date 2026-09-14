from __future__ import annotations

import bpy


def validate_scene(
    scene_id: str,
    expected_ids: set[str],
    expected_room_ids: set[str] | None = None,
    contract_room_ids: set[str] | None = None,
    task_checks: list[dict] | None = None,
) -> dict:
    findings = []
    semantic_objects = [obj for obj in bpy.data.objects if obj.get("semantic_id")]
    actual_ids = {obj.get("semantic_id") for obj in semantic_objects}
    for missing in sorted(expected_ids - actual_ids):
        findings.append({
            "severity": "blocking",
            "entity_id": missing,
            "message": "Required scene entity is missing.",
            "suggested_fix": "Regenerate the entity from the scene specification.",
        })

    duplicate_ids = sorted({
        semantic_id
        for semantic_id in actual_ids
        if sum(obj.get("semantic_id") == semantic_id for obj in semantic_objects) > 1
    })
    for semantic_id in duplicate_ids:
        findings.append({
            "severity": "blocking",
            "entity_id": semantic_id,
            "message": "Semantic identifier is assigned to multiple Blender objects.",
            "suggested_fix": "Register one semantic root and mark its parts with semantic_owner.",
        })

    expected_room_ids = expected_room_ids or set()
    contract_room_ids = contract_room_ids or set()
    for missing in sorted(expected_room_ids - contract_room_ids):
        findings.append({
            "severity": "blocking",
            "entity_id": missing,
            "message": "Room is missing from the resolved structure contract.",
            "suggested_fix": "Call context.register_room after authoring its spatial shell.",
        })

    invalid_scale = []
    for obj in bpy.data.objects:
        if obj.type == "MESH" and any(value <= 0 for value in obj.dimensions):
            invalid_scale.append(obj.name)
    for name in invalid_scale:
        findings.append({
            "severity": "blocking",
            "entity_id": name,
            "message": "Mesh has a non-positive dimension.",
            "suggested_fix": "Correct dimensions in the source specification.",
        })

    task_ids = {
        obj.get("semantic_id")
        for obj in semantic_objects
        if obj.get("semantic_role") == "task"
    }
    missing_articulation = []
    # A manipulated object can be a free body (cup, tray), not an articulation.
    # Joint requirements are checked against physics.yaml in the USD phase.
    required_articulations = {
        obj.get("semantic_id") for obj in semantic_objects if obj.get("requires_articulation")
    }
    for semantic_id in sorted(required_articulations):
        related = [
            obj
            for obj in bpy.data.objects
            if obj.get("semantic_id") == semantic_id or obj.get("semantic_owner") == semantic_id
        ]
        if not any(obj.get("interaction_type") for obj in related):
            missing_articulation.append(semantic_id)
    for semantic_id in missing_articulation:
        findings.append({
            "severity": "blocking",
            "entity_id": semantic_id,
            "message": "Task entity has no authored articulation metadata.",
            "suggested_fix": "Add a movable child/root with local axis, parent body, and limits.",
        })

    cavity_entities = {
        "living_tv_console_drawers",
        "kitchen_drawers",
        "master_wardrobe_doors",
    }
    missing_cavities = []
    for semantic_id in sorted(cavity_entities & task_ids):
        related_names = {
            obj.name.lower()
            for obj in bpy.data.objects
            if obj.get("semantic_id") == semantic_id or obj.get("semantic_owner") == semantic_id
        }
        required_tokens = ("bottom", "left_side", "right_side", "back")
        if not all(any(token in name for name in related_names) for token in required_tokens):
            missing_cavities.append(semantic_id)
    for semantic_id in missing_cavities:
        findings.append({
            "severity": "blocking",
            "entity_id": semantic_id,
            "message": "Articulated casework is missing a verifiable hollow-shell panel set.",
            "suggested_fix": "Model bottom, side, and back panels around the revealed cavity.",
        })

    task_checks = task_checks or []
    for check in task_checks:
        if check["passed"]:
            continue
        findings.append({
            "severity": "blocking",
            "entity_id": check["entity_id"],
            "message": (
                f"Task clearance check {check['id']} measured {check['measured']} "
                f"{check['units']}; requires at least {check['required']} {check['units']}."
            ),
            "suggested_fix": "Repair the source layout and rebuild the scene.",
        })

    return {
        "scene_id": scene_id,
        "status": "needs_repair" if findings else "pass",
        "checks": {
            "required_entities_present": not bool(expected_ids - actual_ids),
            "semantic_ids_unique": not bool(duplicate_ids),
            "required_rooms_resolved": not bool(expected_room_ids - contract_room_ids),
            "positive_mesh_dimensions": not bool(invalid_scale),
            "task_articulation_authored": not bool(missing_articulation),
            "articulated_casework_hollow": not bool(missing_cavities),
            "task_clearances": all(check["passed"] for check in task_checks),
        },
        "task_checks": task_checks,
        "findings": findings,
    }
