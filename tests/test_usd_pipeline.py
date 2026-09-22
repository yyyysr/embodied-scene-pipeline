import json
from pathlib import Path

import yaml
from pxr import Gf, Usd, UsdGeom, UsdPhysics, UsdShade

from embodied_scene.usd.pipeline import author_physics, build_object_map


def fixture(tmp_path):
    stage = Usd.Stage.CreateNew(str(tmp_path / "geometry.usdc"))
    UsdGeom.SetStageMetersPerUnit(stage, 1)
    UsdGeom.SetStageUpAxis(stage, "Z")
    UsdGeom.Xform.Define(stage, "/World")
    records = []
    for name in ["wall", "door", "anchor"]:
        root = UsdGeom.Xform.Define(stage, "/World/" + name)
        root.AddTranslateOp().Set(Gf.Vec3d(2, 3, 0))
        root.AddRotateZOp().Set(45)
        if name != "anchor":
            mesh = UsdGeom.Mesh.Define(stage, "/World/" + name + "/shape")
            mesh.CreatePointsAttr([(-0.5, -0.5, 0), (0.5, -0.5, 0), (0, 0.5, 0)])
            mesh.CreateFaceVertexCountsAttr([3])
            mesh.CreateFaceVertexIndicesAttr([0, 1, 2])
        records.append({"semantic_id": name, "export_name": name})
    stage.GetRootLayer().Save()
    (tmp_path / "blender_objects.json").write_text(json.dumps({"objects": records}))
    build_object_map(tmp_path)
    spec = yaml.safe_load(Path("templates/physics.yaml").read_text())
    spec["bodies"] = [
        {
            "id": "wall",
            "object": "wall",
            "type": "static",
            "colliders": [{"object": "wall", "approximation": "none"}],
        },
        {
            "id": "door",
            "object": "door",
            "type": "dynamic",
            "mass_kg": 2,
            "colliders": [{"object": "door", "approximation": "convexHull"}],
        },
    ]
    spec["joints"] = [
        {
            "id": "hinge",
            "type": "revolute",
            "body0": "wall",
            "body1": "door",
            "anchor": "anchor",
            "axis": "Z",
            "limits": [-90, 90],
        }
    ]
    return spec


def run(tmp_path, spec):
    path = tmp_path / "physics.yaml"
    path.write_text(yaml.safe_dump(spec))
    return author_physics(path, tmp_path)


def test_layers_rotated_anchor_and_rebuild(tmp_path):
    spec = fixture(tmp_path)
    geometry_bytes = (tmp_path / "geometry.usdc").read_bytes()
    result = run(tmp_path, spec)
    assert result["status"] == "pass", result
    assert result["dynamic_validation"]["status"] == "pending_user"
    stage = Usd.Stage.Open(str(tmp_path / "scene.usdc"))
    joint = UsdPhysics.RevoluteJoint.Get(stage, "/World/Physics/Joints/hinge")
    assert joint.GetLocalPos0Attr().Get() == Gf.Vec3f(2, 3, 0)
    assert joint.GetLocalPos1Attr().Get().GetLength() < 1e-5
    assert not stage.GetPrimAtPath("/World/wall").HasAPI(UsdPhysics.RigidBodyAPI)
    assert (tmp_path / "geometry.usdc").read_bytes() == geometry_bytes
    spec["joints"] = []
    assert run(tmp_path, spec)["status"] == "pass"
    stage = Usd.Stage.Open(str(tmp_path / "scene.usdc"))
    stage.Reload()
    assert not stage.GetPrimAtPath("/World/Physics/Joints/hinge")


def test_bad_joint_and_unclassified_mesh(tmp_path):
    spec = fixture(tmp_path)
    spec["joints"][0]["body1"] = "missing"
    assert run(tmp_path, spec)["status"] == "fail"
    spec["joints"] = []
    spec["bodies"].pop()
    assert "Unclassified" in run(tmp_path, spec)["errors"][0]


def test_moving_triangle_mesh_rejected(tmp_path):
    spec = fixture(tmp_path)
    spec["bodies"][1]["colliders"][0]["approximation"] = "none"
    assert "convex" in run(tmp_path, spec)["errors"][0]


def test_physx_contact_offsets_and_restitution_combine(tmp_path):
    spec = fixture(tmp_path)
    spec["materials"]["default"]["restitution_combine_mode"] = "max"
    collider = spec["bodies"][1]["colliders"][0]
    collider.update(contact_offset_m=.00015, rest_offset_m=0)
    assert run(tmp_path, spec)["status"] == "pass"
    stage = Usd.Stage.Open(str(tmp_path / "scene.usdc"))
    material = stage.GetPrimAtPath('/World/Physics/Materials/default')
    assert material.GetAttribute('physxMaterial:restitutionCombineMode').Get() == 'max'
    mesh = stage.GetPrimAtPath('/World/door/shape')
    assert abs(mesh.GetAttribute('physxCollision:contactOffset').Get() - .00015) < 1e-9
    assert 'PhysxCollisionAPI' in mesh.GetMetadata('apiSchemas').GetAppliedItems()
    collider['rest_offset_m'] = .001
    assert run(tmp_path, spec)['status'] == 'fail'


def test_dynamic_hidden_proxy_remains_pickable(tmp_path):
    spec = fixture(tmp_path)
    spec["bodies"][1]["colliders"][0].update(hide_visual=True)
    assert run(tmp_path, spec)["status"] == "pass"
    stage = Usd.Stage.Open(str(tmp_path / "scene.usdc"))
    mesh = stage.GetPrimAtPath('/World/door/shape')
    assert UsdGeom.Imageable(mesh).ComputeVisibility() == 'inherited'
    assert UsdGeom.Imageable(mesh).ComputePurpose() == 'guide'


def test_mapping_is_recomputed_not_loaded(tmp_path):
    spec = fixture(tmp_path)
    (tmp_path / "object_map.json").write_text('{"objects":{"door":"/BadPath"}}')
    assert run(tmp_path, spec)["status"] == "pass"


def test_internal_reference_and_decomposition_export(tmp_path):
    spec = fixture(tmp_path)
    geometry = Usd.Stage.Open(str(tmp_path / "geometry.usdc"))
    group = UsdGeom.Xform.Define(geometry, "/World/door/Colliders")
    proxy = UsdGeom.Mesh.Define(geometry, group.GetPath().AppendChild("door_proxy"))
    source = UsdGeom.Mesh.Get(geometry, "/World/door/shape")
    proxy.CreatePointsAttr(source.GetPointsAttr().Get())
    proxy.CreateFaceVertexCountsAttr(source.GetFaceVertexCountsAttr().Get())
    proxy.CreateFaceVertexIndicesAttr(source.GetFaceVertexIndicesAttr().Get())
    geometry.GetRootLayer().Save()
    records_path = tmp_path / "blender_objects.json"
    records = json.loads(records_path.read_text())
    records["objects"].append({"reference_id": "door_proxy", "export_name": "door_proxy"})
    records_path.write_text(json.dumps(records))
    mapping = build_object_map(tmp_path)
    assert mapping["objects"]["door_proxy"] == str(proxy.GetPath())
    spec["bodies"][1]["colliders"] = [{
        "object": "door_proxy", "approximation": "convexDecomposition", "hide_visual": True,
    }]
    assert run(tmp_path, spec)["status"] == "pass"
    stage = Usd.Stage.Open(str(tmp_path / "scene.usdc"))
    collider = stage.GetPrimAtPath(proxy.GetPath())
    assert UsdPhysics.MeshCollisionAPI(collider).GetApproximationAttr().Get() == "convexDecomposition"
    # Moving-body proxies stay visible for direct simulator picking.
    assert UsdGeom.Imageable(collider).ComputeVisibility() == "inherited"
    assert UsdGeom.Imageable(collider).ComputePurpose() == "guide"
    assert UsdGeom.Imageable(stage.GetPrimAtPath("/World/door/shape")).ComputeVisibility() == "inherited"
    material, _ = UsdShade.MaterialBindingAPI(collider).ComputeBoundMaterial("physics")
    assert material.GetPrim().HasAPI(UsdPhysics.MaterialAPI)

    # The same render mesh can instead serve as the collider, without a duplicate.
    spec["bodies"][1]["colliders"] = [{
        "object": "door", "approximation": "convexDecomposition",
    }]
    geometry.RemovePrim(group.GetPath())
    geometry.GetRootLayer().Save()
    assert run(tmp_path, spec)["status"] == "pass"
    stage = Usd.Stage.Open(str(tmp_path / "scene.usdc"))
    stage.Reload()
    mesh = stage.GetPrimAtPath("/World/door/shape")
    assert mesh.HasAPI(UsdPhysics.CollisionAPI)
    assert UsdGeom.Imageable(mesh).ComputeVisibility() == "inherited"
    assert UsdGeom.Imageable(mesh).ComputePurpose() == "default"


def test_schema_rejects_negative_mass_and_unknown_keys(tmp_path):
    spec = fixture(tmp_path)
    spec["bodies"][1]["mass_kg"] = -1
    assert run(tmp_path, spec)["status"] == "fail"
    spec["bodies"][1]["mass_kg"] = 1
    spec["joints"][0]["limit"] = [-90, 90]
    assert run(tmp_path, spec)["status"] == "fail"


def test_validator_detects_modified_joint_frame(tmp_path):
    from embodied_scene.usd.pipeline import validate_usd

    spec = fixture(tmp_path)
    assert run(tmp_path, spec)["status"] == "pass"
    stage = Usd.Stage.Open(str(tmp_path / "scene.usdc"))
    joint = UsdPhysics.RevoluteJoint.Get(stage, "/World/Physics/Joints/hinge")
    joint.GetLocalPos1Attr().Set(Gf.Vec3f(10, 0, 0))
    stage.GetRootLayer().Save()
    report = validate_usd(tmp_path / "scene.usdc")
    assert report["status"] == "fail"
    assert any("frames disagree" in e for e in report["errors"])


def test_fixed_joint_and_dynamic_to_dynamic_frames(tmp_path):
    spec = fixture(tmp_path)
    spec["bodies"][0].update(type="dynamic", mass_kg=10)
    spec["bodies"][0]["colliders"][0]["approximation"] = "convexHull"
    spec["joints"][0] = {
        "id": "mount",
        "type": "fixed",
        "body0": "wall",
        "body1": "door",
        "anchor": "anchor",
    }
    assert run(tmp_path, spec)["status"] == "pass"
    stage = Usd.Stage.Open(str(tmp_path / "scene.usdc"))
    joint = UsdPhysics.FixedJoint.Get(stage, "/World/Physics/Joints/mount")
    assert str(joint.GetBody0Rel().GetTargets()[0]) == "/World/wall"
    assert joint.GetLocalPos0Attr().Get().GetLength() < 1e-5
