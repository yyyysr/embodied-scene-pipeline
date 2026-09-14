"""Run in a fresh Blender process; never save export-only scene changes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import bpy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    if abs(scene.unit_settings.scale_length - 1.0) > 1e-8:
        raise ValueError("USD export requires Blender scale_length=1 (meters)")
    scene.frame_set(1)
    review = bpy.data.collections.get("__REVIEW__")
    excluded = set(review.all_objects) if review else set()
    objects = [o for o in scene.objects if o not in excluded]
    ids = [str(o["semantic_id"]) for o in objects if o.get("semantic_id")]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate semantic IDs")
    # Re-enable full geometry hidden for cutaway review. Selection defines export scope.
    for collection in bpy.data.collections:
        collection.hide_viewport = False
        collection.hide_render = False

    def enable(layer):
        layer.exclude = False
        layer.hide_viewport = False
        for child in layer.children:
            enable(child)

    enable(bpy.context.view_layer.layer_collection)
    # USD has no Blender Collection equivalent: create identity Xform groups
    # for top-level object ownership while retaining all object parenting.
    collection_roots = {}

    def collection_root(collection):
        if collection == scene.collection:
            return None
        if collection.name in collection_roots:
            return collection_roots[collection.name]
        parent_collection = next(
            (c for c in bpy.data.collections if collection.name in c.children), scene.collection
        )
        root = bpy.data.objects.new("collection_" + collection.name.lower(), None)
        scene.collection.objects.link(root)
        root["semantic_id"] = "collection_" + re.sub(r"[^a-z0-9_]", "_", collection.name.lower())
        root["source_collection"] = collection.name
        root.parent = collection_root(parent_collection)
        collection_roots[collection.name] = root
        return root

    for obj in list(objects):
        if obj.parent is None:
            owners = sorted(
                (c for c in obj.users_collection if c != scene.collection), key=lambda c: c.name
            )
            if owners:
                matrix = obj.matrix_world.copy()
                obj.parent = collection_root(owners[0])
                obj.matrix_world = matrix
    objects.extend(collection_roots.values())
    records = []
    names = {o: o.name for o in objects}
    for obj in objects:
        obj.name = "temporary_" + hashlib.sha256(names[obj].encode()).hexdigest()
    for obj in scene.objects:
        obj.hide_set(False)
        obj.hide_viewport = False
        obj.hide_render = False
        obj.hide_select = False
        obj.select_set(False)
    export_tokens = set()
    for obj in objects:
        if obj.parent in excluded:
            raise ValueError(f"Export object {names[obj]} has a review-only parent")
        semantic_id = obj.get("semantic_id")
        token = str(semantic_id or re.sub(r"[^A-Za-z0-9_]", "_", names[obj]))
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token):
            if semantic_id:
                raise ValueError(f"semantic_id is not a valid USD identifier: {token}")
            token = "object_" + token
        if token in export_tokens:
            raise ValueError(f"Ambiguous USD object name: {token}; assign unique semantic_id")
        export_tokens.add(token)
        obj.name = token
        if obj.data is not None:
            obj.data = obj.data.copy()
            obj.data.name = token + "_geometry"
        obj.select_set(True)
        records.append(
            {
                "blender_name": names[obj],
                "export_name": token,
                "semantic_id": obj.get("semantic_id"),
                "type": obj.type,
                "parent_semantic_id": obj.parent.get("semantic_id") if obj.parent else None,
            }
        )
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj, record in zip(objects, records):
        if obj.type == "MESH":
            evaluated = obj.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh()
            points = [evaluated.matrix_world @ v.co for v in mesh.vertices]
            if points:
                record["world_bounds"] = [
                    [min(p[i] for p in points) for i in range(3)],
                    [max(p[i] for p in points) for i in range(3)],
                ]
            evaluated.to_mesh_clear()
    properties = bpy.ops.wm.usd_export.get_rna_type().properties
    options = {
        "filepath": str(output / "geometry.usdc"),
        "selected_objects_only": True,
        "export_animation": False,
        "export_materials": True,
        "export_custom_properties": True,
        "overwrite_textures": True,
        "root_prim_path": "/World",
        "relative_paths": True,
        "use_instancing": False,
        "evaluation_mode": "VIEWPORT",
    }
    if "export_textures_mode" in properties:
        options["export_textures_mode"] = "NEW"
    else:
        options["export_textures"] = True
    if "merge_parent_xform" in properties:
        options["merge_parent_xform"] = False
    result = bpy.ops.wm.usd_export(**options)
    if "FINISHED" not in result:
        raise RuntimeError(f"USD export failed: {result}")
    (output / "blender_objects.json").write_text(
        json.dumps(
            {
                "blender_version": bpy.app.version_string,
                "frame": 1,
                "objects": records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
