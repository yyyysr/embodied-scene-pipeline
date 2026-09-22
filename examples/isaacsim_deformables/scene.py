"""Shared Blender source for the soft_block and hanging_cloth examples."""

import bpy


def build_scene(context, spec):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.05))
    floor = bpy.context.object
    floor.scale = (2, 2, 0.1)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    context.register(floor, "floor", "structure")
    root = bpy.data.objects.new("soft_object", None)
    bpy.context.collection.objects.link(root)
    root.location = (0, 0, 0.6)
    context.register(root, "soft_object", "task")
    if spec["description"] == "soft_block":
        bpy.ops.mesh.primitive_cube_add(size=0.2)
        mesh = bpy.context.object
    else:
        count = 20
        points = [
            (i * 0.5 / count - 0.25, j * 0.5 / count - 0.25, 0)
            for j in range(count + 1)
            for i in range(count + 1)
        ]
        faces = []
        for j in range(count):
            for i in range(count):
                a = j * (count + 1) + i
                faces.extend([(a, a + 1, a + count + 2), (a, a + count + 2, a + count + 1)])
        data = bpy.data.meshes.new("cloth")
        data.from_pydata(points, [], faces)
        data.update()
        mesh = bpy.data.objects.new("cloth", data)
        bpy.context.collection.objects.link(mesh)
        anchor = bpy.data.objects.new("cloth_anchor", None)
        bpy.context.collection.objects.link(anchor)
        context.register(anchor, "cloth_anchor", "context")
    mesh.parent = root
    mesh.location = (0, 0, 0)
    bpy.context.view_layer.objects.active = mesh
    modifier = mesh.modifiers.new("simulation_triangles", "TRIANGULATE")
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    context.register_reference(mesh, "soft_object_surface", owner="soft_object")
    mat = bpy.data.materials.new("blue_dielectric")
    mat.diffuse_color = (0.12, 0.3, 0.55, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = mat.diffuse_color
    shader.inputs["Roughness"].default_value = 0.65
    mesh.data.materials.append(mat)
    light_data = bpy.data.lights.new("formal_key", "AREA")
    light_data.energy = 500
    light_data.shape = "DISK"
    light_data.size = 3
    light = bpy.data.objects.new("formal_key", light_data)
    bpy.context.collection.objects.link(light)
    light.location = (0, 0, 3)
