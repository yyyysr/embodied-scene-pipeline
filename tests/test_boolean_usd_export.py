"""Native Blender regression; run with BLENDER_BIN pointing at a supported Blender."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from pxr import Usd, UsdGeom

from embodied_scene.usd.delivery import export_scene


def test_boolean_plates_survive_native_export_and_failed_reexport(tmp_path):
    blender = shutil.which(os.environ.get("BLENDER_BIN", "blender"))
    if not blender:
        pytest.skip("Set BLENDER_BIN to run native Boolean export regression")
    blend = tmp_path / "build/scene.blend"
    blend.parent.mkdir()
    script = tmp_path / "build_plate.py"
    script.write_text("""import bpy
import sys
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
review = bpy.data.collections.new("__REVIEW__")
bpy.context.scene.collection.children.link(review)
for level in range(2):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, .2 + level * .3))
    plate = bpy.context.object
    plate.name = "plate_" + str(level)
    plate["semantic_id"] = plate.name
    plate.dimensions = (.3, .14, .02)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    # Two materials and UVs must survive export-only triangulation.
    for color in ((.2, .3, .4, 1), (.8, .6, .3, 1)):
        material = bpy.data.materials.new("plate_material")
        material.diffuse_color = color
        plate.data.materials.append(material)
    for polygon in plate.data.polygons:
        polygon.material_index = polygon.index % 2
    for x in (-.08, 0, .08):
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=.025, depth=.08,
                                          location=(x, 0, plate.location.z))
        cutter = bpy.context.object
        modifier = plate.modifiers.new("hole", "BOOLEAN")
        modifier.operation = "DIFFERENCE"
        modifier.solver = "EXACT"
        modifier.object = cutter
        # Upper plate retains a live modifier stack; lower uses applied Boolean.
        if level == 0:
            bpy.context.view_layer.objects.active = plate
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            bpy.data.objects.remove(cutter, do_unlink=True)
        else:
            for collection in list(cutter.users_collection):
                collection.objects.unlink(cutter)
            review.objects.link(cutter)
    assert not any(m.type == "TRIANGULATE" for m in plate.modifiers)
bpy.ops.mesh.primitive_cube_add(size=.04, location=(.7, 0, .2))
rounded = bpy.context.object
rounded["semantic_id"] = "rounded"
rounded.scale = (1, 1.5, .8)
rounded.rotation_euler = (.2, .3, .4)
rounded.data.materials.append(bpy.data.materials[0])
rounded.modifiers.new("subdivision", "SUBSURF").levels = 2
bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1])
""")
    subprocess.run(
        [
            blender,
            "--background",
            "-noaudio",
            "--python-exit-code",
            "1",
            "--python",
            str(script),
            "--",
            str(blend),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    original = blend.read_bytes()
    specs = tmp_path / "specs"
    specs.mkdir()
    physics = yaml.safe_load(Path("templates/physics.yaml").read_text())
    physics["bodies"] = [
        {
            "id": f"plate_{i}",
            "object": f"plate_{i}",
            "type": "static",
            "colliders": [{"object": f"plate_{i}", "approximation": "none"}],
        }
        for i in range(2)
    ]
    physics["visual_only"] = ["rounded"]
    (specs / "physics.yaml").write_text(yaml.safe_dump(physics))
    passages = [
        {
            "id": f"hole_{i}_{j}_{representation}",
            "objects": [f"plate_{i}"],
            "representation": representation,
            "start": [x, 0, 0.16 + i * 0.3],
            "end": [x, 0, 0.24 + i * 0.3],
            "radius_m": 0.02,
        }
        for i in range(2)
        for j, x in enumerate((-0.08, 0, 0.08))
        for representation in ("visual", "collision")
    ]
    task = {
        "id": "rack",
        "task_type": "tabletop",
        "actor": {"type": "robot_arm"},
        "goal": "Insert tubes through both plates",
        "passages": passages,
    }
    (specs / "task.yaml").write_text(yaml.safe_dump(task))
    result = export_scene(blend, specs / "physics.yaml", tmp_path, blender=blender)
    assert result["status"] == "pass", result
    assert len(result["geometry"]["passages"]) == 12
    assert result["geometry"]["surface_fidelity"]["meshes"] == 3
    assert blend.read_bytes() == original
    output = tmp_path / "exports/scene.usdc"
    stage = Usd.Stage.Open(str(output))
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            mesh = UsdGeom.Mesh(prim)
            assert set(mesh.GetFaceVertexCountsAttr().Get()) == {3}
            assert mesh.GetSubdivisionSchemeAttr().Get() == "none"
            assert mesh.GetPrim().GetAttribute("primvars:st").Get()
            assert mesh.GetNormalsAttr().Get()
            assert mesh.GetPrim().GetRelationship("material:binding").GetTargets() or any(
                child.IsA(UsdGeom.Subset) for child in mesh.GetPrim().GetChildren()
            )
    before = output.read_bytes()

    # Simulate a downstream exporter/adapter regression: cap a hole with two triangles.
    def cap_hole(stage):
        prim = next(p for p in stage.Traverse() if p.IsA(UsdGeom.Mesh))
        mesh = UsdGeom.Mesh(prim)
        points = list(mesh.GetPointsAttr().Get())
        offset = len(points)
        points += [
            (-0.02, -0.02, 0.21),
            (0.02, -0.02, 0.21),
            (0.02, 0.02, 0.21),
            (-0.02, 0.02, 0.21),
        ]
        mesh.GetPointsAttr().Set(points)
        mesh.GetFaceVertexCountsAttr().Set(list(mesh.GetFaceVertexCountsAttr().Get()) + [3, 3])
        mesh.GetFaceVertexIndicesAttr().Set(
            list(mesh.GetFaceVertexIndicesAttr().Get())
            + [offset, offset + 1, offset + 2, offset, offset + 2, offset + 3]
        )

    result = export_scene(
        blend, specs / "physics.yaml", tmp_path, blender=blender, configure_stage=cap_hole
    )
    assert result["status"] == "fail", result
    assert "Triangle count" in str(result["errors"])
    assert output.read_bytes() == before
    assert json.loads((tmp_path / "review/report.json").read_text())["usd"]["status"] == "fail"
    assert not (tmp_path / "build/usd_debug").exists()
