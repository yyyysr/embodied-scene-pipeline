"""Blender-only integration fixture; output is generated, not committed."""

import sys
from pathlib import Path

import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.scale_length = 1


def root(name, position):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.location = position
    obj["semantic_id"] = name
    return obj


def box(name, position, size, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.object
    obj.name = name
    obj.parent = parent
    obj.location = position
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj["semantic_id"] = name
    return obj


box("floor", (0, 0, -0.1), (5, 5, 0.2))
wall = box("wall", (0, 1.5, 1.5), (5, 0.2, 3))
# This full wall is deliberately hidden in Blender's review state.
wall.hide_render = True
wall.hide_set(True)
box("cabinet", (-1.5, 0.6, 0.5), (0.5, 0.6, 1))
door = root("door", (0, 1.25, 1))
box("door_panel", (0.45, 0, 0), (0.9, 0.06, 1.8), door)
root("door_anchor", (0, 1.25, 1))
drawer = root("drawer", (-1.5, 0.05, 0.6))
# Open-topped, compound drawer; do not convexify the complete drawer.
for name, pos, size in [
    ("drawer_bottom", (0, 0, 0), (0.4, 0.4, 0.02)),
    ("drawer_left", (-0.19, 0, 0.08), (0.02, 0.4, 0.16)),
    ("drawer_right", (0.19, 0, 0.08), (0.02, 0.4, 0.16)),
    ("drawer_front", (0, -0.19, 0.08), (0.4, 0.02, 0.16)),
    ("drawer_back", (0, 0.19, 0.08), (0.4, 0.02, 0.16)),
]:
    box(name, pos, size, drawer)
root("drawer_anchor", (-1.5, 0.05, 0.6))
free = root("free_box", (1, 0, 1))
box("free_shape", (0, 0, 0), (0.2, 0.2, 0.2), free)
review = bpy.data.collections.new("__REVIEW__")
bpy.context.scene.collection.children.link(review)
bpy.ops.object.camera_add(location=(4, -6, 4))
camera = bpy.context.object
for collection in list(camera.users_collection):
    collection.objects.unlink(camera)
review.objects.link(camera)
path = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
path.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(path))
