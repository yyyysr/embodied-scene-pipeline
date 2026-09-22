from __future__ import annotations

import bpy
from mathutils import Vector


def _point_at(obj, target=(0.0, 0.0, 0.7)) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _scene_bounds():
    points = []
    for obj in bpy.data.objects:
        if obj.type != "MESH" or any(
            collection.name == "__REVIEW__" for collection in obj.users_collection
        ):
            continue
        points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    if not points:
        return Vector((-1.0, -1.0, 0.0)), Vector((1.0, 1.0, 1.5))
    return (
        Vector(tuple(min(point[axis] for point in points) for axis in range(3))),
        Vector(tuple(max(point[axis] for point in points) for axis in range(3))),
    )


def _room_camera(room_id: str, polygon) -> tuple[object, str]:
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    center = Vector(((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5, 1.05))
    data = bpy.data.cameras.new(f"review_camera__room_{room_id}")
    camera = bpy.data.objects.new(f"review_camera__room_{room_id}", data)
    camera.location = (
        min(xs) + (max(xs) - min(xs)) * 0.32,
        min(ys) + (max(ys) - min(ys)) * 0.32,
        1.80,
    )
    _point_at(camera, center)
    data.lens = 18.0
    return camera, room_id


def _room_inside_camera(room_id: str, polygon) -> object:
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    center = Vector(((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5, 1.05))
    data = bpy.data.cameras.new(f"review_camera__room_{room_id}_alt")
    camera = bpy.data.objects.new(f"review_camera__room_{room_id}_alt", data)
    camera.location = (
        max(xs) - (max(xs) - min(xs)) * 0.32,
        max(ys) - (max(ys) - min(ys)) * 0.32,
        1.80,
    )
    _point_at(camera, center)
    data.lens = 18.0
    return camera


def add_review_cameras(scene_spec: dict | None = None) -> dict[str, object]:
    review = bpy.data.collections["__REVIEW__"]
    cameras = {}
    lower, upper = _scene_bounds()
    center = (lower + upper) * 0.5
    span = max(upper.x - lower.x, upper.y - lower.y, 2.0)
    target = (center.x, center.y, max(0.7, min(center.z, 1.2)))
    definitions = {
        "overview": (
            (center.x + span * 0.78, center.y - span * 0.78, upper.z + span * 0.58),
            target,
            52.0,
        ),
        "top": ((center.x, center.y, upper.z + span), (center.x, center.y, 0.0), 55.0),
        "task": (
            (
                center.x - span * 0.62,
                center.y - span * 0.72,
                upper.z + span * 0.48,
            ),
            target,
            52.0,
        ),
    }
    for view, (location, target, lens) in definitions.items():
        authored = bpy.data.objects.get(f"review_camera__{view}")
        if authored is not None and authored.type == "CAMERA":
            cameras[view] = authored
            continue
        data = bpy.data.cameras.new(f"review_camera__{view}")
        camera = bpy.data.objects.new(f"review_camera__{view}", data)
        review.objects.link(camera)
        camera.location = location
        if view == "top":
            data.type = "ORTHO"
            data.ortho_scale = span * 1.12
        else:
            data.lens = lens
        _point_at(camera, target)
        cameras[view] = camera
    # Scene scripts may author focused evidence cameras for specific interfaces
    # (drawer travel, brick coupling, collision source). They remain review-only
    # and are selected by SCENE_REVIEW_VIEWS without hard-coding scene IDs here.
    for obj in bpy.data.objects:
        if obj.type == "CAMERA" and obj.name.startswith("review_camera__"):
            view = obj.name.removeprefix("review_camera__")
            cameras.setdefault(view, obj)
    for room in (scene_spec or {}).get("rooms", []):
        polygon = room.get("floor_polygon")
        if not polygon:
            continue
        camera, room_id = _room_camera(room["id"], polygon)
        review.objects.link(camera)
        cameras[f"room_{room_id}"] = camera
        inside = _room_inside_camera(room["id"], polygon)
        review.objects.link(inside)
        cameras[f"room_{room_id}_alt"] = inside
    return cameras
