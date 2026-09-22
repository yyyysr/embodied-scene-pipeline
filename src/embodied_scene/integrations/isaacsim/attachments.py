"""Explicit node-to-Xform attachments selected from authored surface topology."""

from pxr import Gf, UsdGeom, Vt

from .schema import set_attr


def selection(stage, root, sim, target, region):
    cache = UsdGeom.XformCache()
    world = cache.GetLocalToWorldTransform(sim)
    to_body = world * cache.GetLocalToWorldTransform(root).GetInverse()
    to_target = world * cache.GetLocalToWorldTransform(target).GetInverse()
    selected, local = [], []
    for i, point in enumerate(UsdGeom.PointBased(sim).GetPointsAttr().Get()):
        point = Gf.Vec3d(point)
        p = to_body.Transform(point)
        if all(lo <= x <= hi for lo, x, hi in zip(region["min"], p, region["max"])):
            selected.append(i)
            local.append(Gf.Vec3f(to_target.Transform(point)))
    if not selected:
        raise ValueError("Attachment region selects no simulation nodes")
    return selected, local


def author(stage, config, bodies, mapping):
    for spec in config.get("attachments", []):
        root, sim = bodies[spec["body"]]
        target = stage.GetPrimAtPath(mapping[spec["target"]])
        ids, positions = selection(stage, root, sim, target, spec["region"])
        path = "/World/Physics/DeformableAttachments/" + spec["id"]
        if stage.GetPrimAtPath(path):
            raise ValueError(f"Reserved attachment path already exists: {path}")
        prim = stage.DefinePrim(path, "OmniPhysicsVtxXformAttachment")
        prim.CreateRelationship("omniphysics:src0").SetTargets([root.GetPath()])
        prim.CreateRelationship("omniphysics:src1").SetTargets([target.GetPath()])
        set_attr(prim, "omniphysics:vtxIndicesSrc0", Vt.IntArray(ids))
        set_attr(prim, "omniphysics:localPositionsSrc1", Vt.Vec3fArray(positions))
