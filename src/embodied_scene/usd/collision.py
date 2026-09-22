"""USD adapter for generated, individually convex collision meshes."""
import json

from pxr import Gf, Sdf, UsdGeom

from embodied_scene.collision.coacd import decompose_mesh


def configure_proxy(prim):
    """Dedicated collision geometry is guide geometry with physics-only binding."""
    from pxr import Usd, UsdShade

    imageable = UsdGeom.Imageable(prim)
    imageable.CreatePurposeAttr(UsdGeom.Tokens.guide)
    imageable.CreateVisibilityAttr(UsdGeom.Tokens.inherited)
    for child in Usd.PrimRange(prim):
        for relationship in child.GetRelationships():
            name = relationship.GetName()
            if name.startswith("material:binding") and "physics" not in name.split(":"):
                relationship.BlockTargets()
        binding = UsdShade.MaterialBindingAPI.Apply(child)
        for purpose in ("", "preview", "full"):
            binding.UnbindDirectBinding(purpose)


def generate(stage, source, body_path, collider):
    mesh = UsdGeom.Mesh(source)
    if any(n != 3 for n in mesh.GetFaceVertexCountsAttr().Get()):
        raise ValueError(f"CoACD source must be triangulated: {source.GetPath()}")
    cache = UsdGeom.XformCache()
    # Translate-only frame keeps distances in meters even on scaled static roots.
    matrix = cache.GetLocalToWorldTransform(source)
    origin = matrix.ExtractTranslation()
    points = [list(matrix.Transform(Gf.Vec3d(p)) - origin) for p in mesh.GetPointsAttr().Get()]
    import numpy as np
    faces = np.asarray(mesh.GetFaceVertexIndicesAttr().Get()).reshape(-1, 3)
    parts, info = decompose_mesh(points, faces, collider.get("parameters"))
    root = stage.GetPrimAtPath(body_path)
    if root.IsA(UsdGeom.Gprim):
        raise ValueError("CoACD requires an Xform body root above source geometry")
    group_path = body_path.AppendChild("Colliders").AppendChild(collider["object"])
    if stage.GetPrimAtPath(group_path):
        raise ValueError(f"Generated collider path already exists: {group_path}")
    parent_path = group_path.GetParentPath()
    existing = stage.GetPrimAtPath(parent_path)
    if existing and not existing.IsA(UsdGeom.Xform):
        raise ValueError(f"Colliders container must be an Xform: {parent_path}")
    if not stage.GetPrimAtPath(parent_path):
        UsdGeom.Xform.Define(stage, parent_path)
    group = UsdGeom.Xform.Define(stage, group_path)
    frame = Gf.Matrix4d(1).SetTranslate(origin)
    parent_matrix = cache.GetLocalToWorldTransform(stage.GetPrimAtPath(parent_path))
    if abs(parent_matrix.GetDeterminant()) < 1e-12:
        raise ValueError("CoACD parent transform must be invertible")
    local = frame * parent_matrix.GetInverse()
    group.AddTransformOp().Set(local)
    group.GetPrim().CreateAttribute("collision:coacd", Sdf.ValueTypeNames.String).Set(
        json.dumps(info, sort_keys=True)
    )
    group.GetPrim().CreateRelationship("collision:source").SetTargets([source.GetPath()])
    result = []
    for index, (vertices, triangles) in enumerate(parts):
        proxy = UsdGeom.Mesh.Define(stage, group_path.AppendChild(f"part_{index:03d}"))
        proxy.CreatePointsAttr([Gf.Vec3f(*p) for p in vertices])
        proxy.CreateFaceVertexCountsAttr([3] * len(triangles))
        proxy.CreateFaceVertexIndicesAttr(triangles.reshape(-1).tolist())
        proxy.CreateSubdivisionSchemeAttr("none")
        configure_proxy(proxy.GetPrim())
        result.append(proxy.GetPrim())
    return result


def validate_generated(stage, group):
    import numpy as np
    from pxr import UsdPhysics, UsdShade

    from embodied_scene.collision.validation import validate_parts

    info = json.loads(group.GetAttribute("collision:coacd").Get())
    sources = group.GetRelationship("collision:source").GetTargets()
    if len(sources) != 1 or not stage.GetPrimAtPath(sources[0]).IsA(UsdGeom.Mesh):
        raise ValueError(f"Invalid CoACD source: {group.GetPath()}")
    children = list(group.GetChildren())
    if len(children) != info["parts"]:
        raise ValueError(f"Missing CoACD parts: {group.GetPath()}")
    arrays = []
    for child in children:
        mesh = UsdGeom.Mesh(child)
        if (not mesh or any(n != 3 for n in mesh.GetFaceVertexCountsAttr().Get())
                or not child.HasAPI(UsdPhysics.CollisionAPI)
                or not UsdPhysics.CollisionAPI(child).GetCollisionEnabledAttr().Get()
                or UsdPhysics.MeshCollisionAPI(child).GetApproximationAttr().Get() != "convexHull"
                or mesh.ComputePurpose() != "guide"
                or mesh.ComputeVisibility() != "inherited"
                or not UsdShade.MaterialBindingAPI(child).ComputeBoundMaterial("physics")[0]):
            raise ValueError(f"Invalid CoACD collider: {child.GetPath()}")
        arrays.append((np.asarray(mesh.GetPointsAttr().Get()),
                       np.asarray(mesh.GetFaceVertexIndicesAttr().Get()).reshape(-1, 3)))
    validate_parts(arrays)
    return info
