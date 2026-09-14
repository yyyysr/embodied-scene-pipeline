from __future__ import annotations

import bpy
from mathutils import Vector


def _scene_bounds():
    points = [
        obj.matrix_world @ Vector(corner)
        for obj in bpy.data.objects
        if obj.type == "MESH"
        for corner in obj.bound_box
    ]
    if not points:
        return Vector((-1.0, -1.0, 0.0)), Vector((1.0, 1.0, 2.0))
    return (
        Vector(tuple(min(point[axis] for point in points) for axis in range(3))),
        Vector(tuple(max(point[axis] for point in points) for axis in range(3))),
    )


def add_review_lighting() -> None:
    review = bpy.data.collections["__REVIEW__"]
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (0.035, 0.035, 0.035)

    lower, upper = _scene_bounds()
    center = (lower + upper) * 0.5
    span = max(upper.x - lower.x, upper.y - lower.y, 2.0)

    for name, location, energy, size in (
        ("key", (center.x - span * 0.25, center.y - span * 0.2, upper.z + 2.2), 1800.0, span * 0.65),
        ("fill", (center.x + span * 0.3, center.y + span * 0.15, upper.z + 1.4), 1200.0, span * 0.5),
    ):
        data = bpy.data.lights.new(f"review_light__{name}", type="AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        light = bpy.data.objects.new(f"review_light__{name}", data)
        light.location = location
        light.rotation_euler = (0.25, 0.0, 0.75 if name == "key" else -1.0)
        review.objects.link(light)

    sun_data = bpy.data.lights.new("review_light__sun", type="SUN")
    sun_data.energy = 1.6
    sun_data.angle = 0.35
    sun = bpy.data.objects.new("review_light__sun", sun_data)
    sun.rotation_euler = (0.55, -0.35, -0.65)
    review.objects.link(sun)
