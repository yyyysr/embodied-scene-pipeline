from __future__ import annotations

import bpy


def material_for(asset_id: str, color: list[float]):
    material = bpy.data.materials.new(name=f"mat__{asset_id}")
    rgba = tuple(color[:3]) + (color[3] if len(color) > 3 else 1.0,)
    material.diffuse_color = rgba
    material.use_nodes = True
    node = material.node_tree.nodes.get("Principled BSDF")
    if node:
        node.inputs["Base Color"].default_value = rgba
        node.inputs["Roughness"].default_value = 0.55
    return material

