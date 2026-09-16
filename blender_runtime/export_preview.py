"""Transient GLB with the same explicit collider display policy as USD delivery."""

import json
import sys
from pathlib import Path

import bpy

output, settings_path = sys.argv[sys.argv.index("--") + 1 :]
settings = json.loads(Path(settings_path).read_text())
hidden = set(settings["hidden"])
display_bodies = set(settings["display_bodies"])
review = bpy.data.collections.get("__REVIEW__")
excluded = set(review.all_objects) if review else set()
bpy.context.scene.frame_set(1)
for collection in bpy.data.collections:
    collection.hide_viewport = False
    collection.hide_render = False


def enable(layer):
    layer.exclude = False
    layer.hide_viewport = False
    for child in layer.children:
        enable(child)


enable(bpy.context.view_layer.layer_collection)
for obj in bpy.context.scene.objects:
    obj.hide_set(False)
    obj.hide_viewport = False
    obj.hide_render = False
    obj.select_set(False)

for obj in bpy.context.scene.objects:
    if obj in excluded or obj.type not in {"MESH", "EMPTY"}:
        continue
    ancestors = []
    current = obj
    while current:
        ancestors.append(current)
        current = current.parent
    ids = {str(o.get("semantic_id", o.name)) for o in ancestors}
    if ids & hidden:
        continue
    if ids & display_bodies and any(o.name.endswith("_visual") for o in ancestors):
        continue
    obj.select_set(True)

bpy.ops.export_scene.gltf(
    filepath=output,
    export_format="GLB",
    use_selection=True,
    export_yup=True,
    export_extras=True,
    export_animations=False,
    export_cameras=False,
    export_lights=False,
)
