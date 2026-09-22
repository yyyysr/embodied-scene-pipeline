"""Author volume generation recipes and explicit surface simulation geometry."""

from pxr import Gf, Usd, UsdGeom, UsdPhysics, Vt

from .schema import apply, set_attr


def mesh_for(stage, path):
    meshes = [p for p in Usd.PrimRange(stage.GetPrimAtPath(path)) if p.IsA(UsdGeom.Mesh)]
    if len(meshes) != 1:
        raise ValueError(f"Expected exactly one source mesh: {path}")
    return UsdGeom.Mesh(meshes[0])


def triangles(mesh, *, closed=False):
    import numpy as np

    points = np.asarray(mesh.GetPointsAttr().Get(), dtype=float)
    faces = list(mesh.GetFaceVertexCountsAttr().Get() or [])
    indices = list(mesh.GetFaceVertexIndicesAttr().Get() or [])
    if not faces or any(n != 3 for n in faces) or len(indices) != 3 * len(faces):
        raise ValueError("Source must be explicitly triangulated before export")
    tri = np.asarray(indices, dtype=int).reshape(-1, 3)
    if (tri < 0).any() or (tri >= len(points)).any() or not np.isfinite(points).all():
        raise ValueError("Invalid source mesh points or indices")
    areas = np.linalg.norm(
        np.cross(points[tri[:, 1]] - points[tri[:, 0]], points[tri[:, 2]] - points[tri[:, 0]]),
        axis=1,
    )
    if (areas <= 1e-12).any():
        raise ValueError("Degenerate source triangles")
    edges = {}
    for a, b, c in tri:
        for i, j in ((a, b), (b, c), (c, a)):
            edges.setdefault(tuple(sorted((i, j))), []).append((int(i), int(j)))
    if any(len(e) > 2 or (len(e) == 2 and e[0] == e[1]) for e in edges.values()):
        raise ValueError("Non-manifold or inconsistently oriented source mesh")
    if closed and any(len(e) != 2 for e in edges.values()):
        raise ValueError("Volume source must be closed")
    return points, tri


def bind_pose(prim):
    apply(prim, "OmniPhysicsDeformablePoseAPI:default")
    set_attr(prim, "deformablePose:default:omniphysics:purposes", ["bindPose"])
    set_attr(
        prim,
        "deformablePose:default:omniphysics:points",
        UsdGeom.PointBased(prim).GetPointsAttr().Get(),
    )


def author(stage, body, mapping):
    root = stage.GetPrimAtPath(mapping[body["object"]])
    matrix = UsdGeom.XformCache().GetLocalToWorldTransform(root)
    axes = [Gf.Vec3d(*matrix[i][:3]) for i in range(3)]
    if (
        any(abs(axis.GetLength() - 1) > 1e-5 for axis in axes)
        or any(abs(Gf.Dot(axes[i], axes[j])) > 1e-5 for i in range(3) for j in range(i))
        or matrix.GetDeterminant() < 0
    ):
        raise ValueError(f"Deformable root must have unit world scale: {root.GetPath()}")
    source = mesh_for(stage, mapping[body["source_mesh"]])
    points, indices = triangles(source, closed=body["kind"] == "volume")
    path = str(root.GetPath()) + "/SimulationMesh"
    if stage.GetPrimAtPath(path):
        raise ValueError(f"Reserved simulation mesh path already exists: {path}")
    if body["kind"] == "volume":
        resolution = body.get("cooking", {}).get("volume_hex_resolution")
        collision_path = str(root.GetPath()) + "/CollisionMesh" if resolution else path
        if stage.GetPrimAtPath(collision_path):
            raise ValueError(f"Reserved collision path already exists: {collision_path}")
        apply(root, "OmniPhysicsDeformableBodyAPI")
        apply(root, "PhysxAutoDeformableBodyAPI")
        set_attr(root, "physxDeformableBody:autoDeformableBodyEnabled", True)
        root.CreateRelationship("physxDeformableBody:cookingSourceMesh", custom=False).SetTargets(
            [source.GetPath()]
        )
        sim = stage.DefinePrim(path, "TetMesh")
        apply(sim, "OmniPhysicsVolumeDeformableSimAPI")
        collider = stage.DefinePrim(collision_path, "TetMesh")
        UsdPhysics.CollisionAPI.Apply(collider)
        if resolution:
            apply(root, "PhysxAutoDeformableHexahedralMeshAPI")
            set_attr(root, "physxDeformableBody:resolution", resolution)
        for prim in {sim, collider}:
            UsdGeom.Imageable(prim).CreatePurposeAttr("guide")
            apply(prim, "OmniPhysicsDeformablePoseAPI:default")
            set_attr(prim, "deformablePose:default:omniphysics:purposes", ["bindPose"])
        for prim in Usd.PrimRange(root):
            if prim not in {sim, collider} and prim.IsA(UsdGeom.PointBased):
                bind_pose(prim)
        return root, sim
    else:
        sim = UsdGeom.Mesh.Define(stage, path)
        cache = UsdGeom.XformCache()
        transform = (
            cache.GetLocalToWorldTransform(source.GetPrim())
            * cache.GetLocalToWorldTransform(root).GetInverse()
        )
        local = [Gf.Vec3f(transform.Transform(Gf.Vec3d(*p))) for p in points]
        sim.CreatePointsAttr(local)
        sim.CreateFaceVertexCountsAttr([3] * len(indices))
        sim.CreateFaceVertexIndicesAttr(indices.flatten().tolist())
        sim.CreateSubdivisionSchemeAttr("none")
        apply(root, "OmniPhysicsDeformableBodyAPI")
        apply(sim.GetPrim(), "OmniPhysicsSurfaceDeformableSimAPI")
        set_attr(sim.GetPrim(), "omniphysics:restShapePoints", local)
        set_attr(
            sim.GetPrim(),
            "omniphysics:restTriVtxIndices",
            [Gf.Vec3i(*map(int, t)) for t in indices],
        )
        set_attr(
            sim.GetPrim(), "omniphysics:restBendAnglesDefault", body.get("rest_bend", "flatDefault")
        )
        UsdPhysics.CollisionAPI.Apply(sim.GetPrim())
        sim.CreatePurposeAttr("guide")
        for prim in Usd.PrimRange(root):
            if prim.IsA(UsdGeom.PointBased):
                bind_pose(prim)
    sim = stage.GetPrimAtPath(path)
    count = len(UsdGeom.PointBased(sim).GetPointsAttr().Get() or [])
    if not count:
        raise ValueError("Cooking generated no simulation points")
    velocity = body.get("initial_velocity_m_s", [0, 0, 0])
    UsdGeom.PointBased(sim).CreateVelocitiesAttr(Vt.Vec3fArray([Gf.Vec3f(*velocity)] * count))
    return root, sim
