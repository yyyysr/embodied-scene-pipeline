from __future__ import annotations

import math

import bpy

from .materials import material_for
from .naming import object_name


def _link_to_collection(obj, collection_name: str) -> None:
    target = bpy.data.collections[collection_name]
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    target.objects.link(obj)


def build_asset(spec: dict):
    kind = spec["kind"]
    dimensions = spec["dimensions"]
    position = spec["position"]
    rotation = spec.get("rotation_euler", [0.0, 0.0, 0.0])

    if kind == "box":
        bpy.ops.mesh.primitive_cube_add(location=position)
    elif kind == "cylinder":
        radius = max(dimensions[0], dimensions[1]) / 2.0
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=radius, depth=dimensions[2], location=position)
    else:
        raise ValueError(f"Unsupported baseline asset kind: {kind}")

    obj = bpy.context.active_object
    obj.name = object_name(kind, spec["id"])
    if kind == "box":
        obj.dimensions = dimensions
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.rotation_euler = [math.radians(value) for value in rotation]
    obj["semantic_id"] = spec["id"]
    obj["semantic_role"] = spec.get("role", "context")
    obj.data.materials.append(material_for(spec["id"], spec.get("color", [0.5, 0.5, 0.5, 1.0])))
    collection = "TASK" if spec.get("role") == "task" else "STRUCTURE" if spec.get("role") == "structure" else "ASSETS"
    _link_to_collection(obj, collection)
    return obj

