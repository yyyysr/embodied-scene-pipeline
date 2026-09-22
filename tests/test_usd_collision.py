import json

import numpy as np
import trimesh
import yaml
from pxr import Gf, Usd, UsdGeom, UsdPhysics

from embodied_scene.usd.delivery import publish_stage
from embodied_scene.usd.pipeline import author_stage, validate_usd


def test_generated_proxy_transform_binding_and_transaction(tmp_path):
    stage = Usd.Stage.CreateNew(str(tmp_path / "geometry.usdc"))
    UsdGeom.SetStageMetersPerUnit(stage, 1)
    UsdGeom.SetStageUpAxis(stage, "Z")
    UsdGeom.Xform.Define(stage, "/World")
    root = UsdGeom.Xform.Define(stage, "/World/body")
    root.AddTranslateOp().Set(Gf.Vec3d(2, 3, 1))
    root.AddRotateZOp().Set(30)
    mesh = UsdGeom.Mesh.Define(stage, "/World/body/source")
    mesh.AddScaleOp().Set(Gf.Vec3f(0.1, 0.2, 0.3))
    box = trimesh.creation.box()
    mesh.CreatePointsAttr(box.vertices.tolist())
    mesh.CreateFaceVertexCountsAttr([3] * len(box.faces))
    mesh.CreateFaceVertexIndicesAttr(box.faces.reshape(-1).tolist())
    stage.GetRootLayer().Save()
    spec = {"version": 1, "materials": {"default": {
        "static_friction": 0.5, "dynamic_friction": 0.3, "restitution": 0}},
        "default_material": "default", "bodies": [{"id": "body", "object": "body",
        "type": "dynamic", "mass_kg": 2, "colliders": [
            {"object": "source", "approximation": "coacd"}]}], "joints": []}
    path = tmp_path / "physics.yaml"
    path.write_text(yaml.safe_dump(spec))
    authored = author_stage(path, tmp_path)
    out = tmp_path / "exports"
    result = publish_stage(authored, out)
    assert result["status"] == "pass", result
    final = Usd.Stage.Open(str(out / "scene.usdc"))
    proxies = [p for p in final.Traverse() if p.HasAPI(UsdPhysics.CollisionAPI)]
    assert len(proxies) == 1
    assert result["counts"]["bodies"] == 1
    assert not final.GetPrimAtPath(mesh.GetPath()).HasAPI(UsdPhysics.CollisionAPI)
    cache = UsdGeom.XformCache()
    def bounds(prim):
        matrix = cache.GetLocalToWorldTransform(prim)
        p = np.array([matrix.Transform(Gf.Vec3d(v))
                      for v in UsdGeom.Mesh(prim).GetPointsAttr().Get()])
        return np.array([p.min(0), p.max(0)])
    assert np.allclose(bounds(proxies[0]), bounds(final.GetPrimAtPath(mesh.GetPath())) )
    assert {p.name for p in out.iterdir()} == {"scene.usdc"}
    previous = (out / "scene.usdc").read_bytes()
    group = proxies[0].GetParent()
    final.RemovePrim(proxies[0].GetPath())
    assert json.loads(group.GetAttribute("collision:coacd").Get())["parts"] == 1
    rejected = publish_stage(final, out)
    assert rejected["status"] == "fail"
    assert (out / "scene.usdc").read_bytes() == previous
    final.Reload()
    assert validate_usd(out / "scene.usdc")["status"] == "pass"
