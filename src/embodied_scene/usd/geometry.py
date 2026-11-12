"""Export fidelity and task-space checks on the actual delivered mesh surfaces."""

from itertools import permutations

import numpy as np
from pxr import Usd, UsdGeom, UsdPhysics
from scipy.spatial import ConvexHull, cKDTree
from trimesh.triangles import closest_point


def mesh_triangles(prim, *, collision=False):
    mesh = UsdGeom.Mesh(prim)
    counts = np.asarray(mesh.GetFaceVertexCountsAttr().Get(), dtype=int)
    indices = np.asarray(mesh.GetFaceVertexIndicesAttr().Get(), dtype=int)
    points = np.asarray(mesh.GetPointsAttr().Get(), dtype=float)
    if not len(counts) or np.any(counts != 3) or len(indices) != 3 * len(counts):
        raise ValueError(f"Expected explicit triangles: {prim.GetPath()}")
    if not np.isfinite(points).all() or np.any(indices < 0) or np.any(indices >= len(points)):
        raise ValueError(f"Invalid triangle points/indices: {prim.GetPath()}")
    if mesh.GetSubdivisionSchemeAttr().Get() != UsdGeom.Tokens.none:
        raise ValueError(f"Unexpected subdivision surface: {prim.GetPath()}")
    if list(mesh.GetHoleIndicesAttr().Get() or []):
        raise ValueError(f"Unexpected excluded faces: {prim.GetPath()}")
    transform = UsdGeom.XformCache().GetLocalToWorldTransform(prim)
    matrix = np.asarray(transform, dtype=float)
    points = points @ matrix[:3, :3] + matrix[3, :3]
    if collision:
        approximation = UsdPhysics.MeshCollisionAPI(prim).GetApproximationAttr().Get()
        if approximation == "convexHull":
            hull = ConvexHull(points)
            faces = hull.simplices.copy()
            normals = np.cross(
                points[faces[:, 1]] - points[faces[:, 0]], points[faces[:, 2]] - points[faces[:, 0]]
            )
            flip = np.einsum("ij,ij->i", normals, hull.equations[:, :3]) < 0
            faces[flip] = faces[flip][:, [0, 2, 1]]
            indices = faces.reshape(-1)
        elif approximation != "none":
            raise ValueError(f"Cannot certify cooked collider {approximation}: {prim.GetPath()}")
    triangles = points[indices.reshape(-1, 3)]
    area2 = np.linalg.norm(
        np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1
    )
    if np.any(area2 <= 1e-18):
        raise ValueError(f"Degenerate triangles: {prim.GetPath()}")
    return triangles


def compare_triangles(expected, actual, tolerance=1e-5):
    """One-to-one surface comparison; tolerate vertex/face ordering and float32 export."""
    expected, actual = np.asarray(expected), np.asarray(actual)
    if expected.shape != actual.shape or not len(expected):
        raise ValueError("Triangle count differs from Blender")
    tree = cKDTree(actual.mean(axis=1))
    orders = np.asarray(list(permutations(range(3))))
    # Fast vectorized path for ordinary meshes. Ambiguous/duplicate centroids use
    # the full one-to-one search below rather than assuming a unique nearest face.
    distances, nearest = tree.query(expected.mean(axis=1))
    if np.all(distances <= tolerance) and len(np.unique(nearest)) == len(expected):
        matched = np.zeros(len(expected), dtype=bool)
        for order in orders:
            matched |= np.all(
                np.linalg.norm(actual[nearest][:, order] - expected, axis=2) <= tolerance, axis=1
            )
        if matched.all():
            return
    used = set()
    # Matching full triangles also catches different connectivity with equal bounds.
    for triangle in expected:
        candidates = tree.query_ball_point(triangle.mean(axis=0), tolerance)
        for index in candidates:
            if index in used:
                continue
            distances = np.linalg.norm(actual[index][orders] - triangle, axis=2)
            if np.any(np.all(distances <= tolerance, axis=1)):
                used.add(index)
                break
        else:
            raise ValueError("Triangle surface differs from Blender")


def validate_surfaces(stage, archive):
    checked = 0
    by_name = {}
    for prim in stage.Traverse():
        by_name.setdefault(prim.GetName(), []).append(prim)
    for key in archive.files:
        name = key.removeprefix("surface_")
        roots = by_name.get(name, [])
        if len(roots) != 1:
            raise ValueError(f"Expected one surface object: {name}")
        root = roots[0]
        meshes = (
            [root]
            if root.IsA(UsdGeom.Mesh)
            else [p for p in root.GetChildren() if p.IsA(UsdGeom.Mesh)]
        )
        if len(meshes) != 1:
            raise ValueError(f"Expected one direct surface mesh: {name}")
        try:
            compare_triangles(archive[key], mesh_triangles(meshes[0]))
        except ValueError as error:
            raise ValueError(f"{name}: {error}") from error
        checked += 1
    return {
        "status": "pass",
        "meshes": checked,
        "tolerance_m": 1e-5,
        "method": "one_to_one_world_triangles",
    }


def segment_surface_distance(start, end, triangles):
    """Exact segment-to-triangle minimum, including endpoint and edge cases."""
    start, end = np.asarray(start, dtype=float), np.asarray(end, dtype=float)
    direction = end - start
    length2 = np.dot(direction, direction)
    if length2 <= 0:
        raise ValueError("Passage endpoints must differ")
    distances = []
    # The minimum is an endpoint/face, segment/edge, or face-intersection pair.
    for point in (start, end):
        nearest = closest_point(triangles, np.broadcast_to(point, (len(triangles), 3)))
        distances.append(np.linalg.norm(nearest - point, axis=1))
    for i in range(3):
        a, b = triangles[:, i], triangles[:, (i + 1) % 3]
        edge = b - a
        edge2 = np.einsum("ij,ij->i", edge, edge)
        for point in (start, end):
            t = np.clip(np.einsum("ij,ij->i", point - a, edge) / edge2, 0, 1)
            distances.append(np.linalg.norm(a + t[:, None] * edge - point, axis=1))
        for point in (a, b):
            t = np.clip((point - start) @ direction / length2, 0, 1)
            distances.append(np.linalg.norm(start + t[:, None] * direction - point, axis=1))
        w = start - a
        cross_dot = edge @ direction
        d = w @ direction
        e = np.einsum("ij,ij->i", edge, w)
        denominator = length2 * edge2 - cross_dot**2
        valid = denominator > 1e-14 * length2 * edge2
        s = np.zeros(len(a))
        t = np.zeros(len(a))
        s[valid] = (cross_dot[valid] * e[valid] - edge2[valid] * d[valid]) / denominator[valid]
        t[valid] = (length2 * e[valid] - cross_dot[valid] * d[valid]) / denominator[valid]
        valid &= (s >= 0) & (s <= 1) & (t >= 0) & (t <= 1)
        distances.append(
            np.where(
                valid,
                np.linalg.norm(start + s[:, None] * direction - a - t[:, None] * edge, axis=1),
                np.inf,
            )
        )
    normal = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    denominator = normal @ direction
    valid = np.abs(denominator) > 1e-14 * np.linalg.norm(normal, axis=1) * np.sqrt(length2)
    t = np.zeros(len(triangles))
    t[valid] = np.einsum("ij,ij->i", normal, triangles[:, 0] - start)[valid] / denominator[valid]
    points = start + t[:, None] * direction
    nearest = closest_point(triangles, points)
    if np.any(valid & (t >= 0) & (t <= 1) & (np.linalg.norm(nearest - points, axis=1) < 1e-10)):
        return 0.0
    return float(np.min(distances))


def validate_passages(stage, checks, mapping):
    results = []
    if len({c["id"] for c in checks}) != len(checks):
        raise ValueError("Duplicate passage IDs")
    for check in checks:
        if not np.isfinite([*check["start"], *check["end"], check["radius_m"]]).all():
            raise ValueError(f"Non-finite passage: {check['id']}")
        meshes = {}
        for object_id in check["objects"]:
            root = stage.GetPrimAtPath(mapping.get(object_id, ""))
            if not root:
                raise ValueError(f"Unknown passage object: {object_id}")
            for prim in Usd.PrimRange(root):
                if not prim.IsA(UsdGeom.Mesh):
                    if check["representation"] == "collision" and prim.HasAPI(
                        UsdPhysics.CollisionAPI
                    ):
                        raise ValueError(
                            f"Passage checks require explicit mesh colliders: {prim.GetPath()}"
                        )
                    continue
                if check["representation"] == "collision":
                    if not prim.HasAPI(UsdPhysics.CollisionAPI):
                        continue
                    if not UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get():
                        continue
                elif UsdGeom.Imageable(prim).ComputePurpose() == UsdGeom.Tokens.guide:
                    continue
                meshes[str(prim.GetPath())] = prim
        if not meshes:
            raise ValueError(f"No {check['representation']} meshes for passage {check['id']}")
        distances = []
        for prim in meshes.values():
            triangles = mesh_triangles(prim, collision=check["representation"] == "collision")
            # Signed solid angle detects endpoints inside a consistently oriented
            # closed solid even if the segment never crosses its boundary.
            for endpoint in (check["start"], check["end"]):
                vectors = triangles - endpoint
                lengths = np.linalg.norm(vectors, axis=2)
                a, b, c = vectors[:, 0], vectors[:, 1], vectors[:, 2]
                numerator = np.einsum("ij,ij->i", a, np.cross(b, c))
                denominator = (
                    np.prod(lengths, axis=1)
                    + np.einsum("ij,ij->i", a, b) * lengths[:, 2]
                    + np.einsum("ij,ij->i", b, c) * lengths[:, 0]
                    + np.einsum("ij,ij->i", c, a) * lengths[:, 1]
                )
                if abs(np.sum(2 * np.arctan2(numerator, denominator))) > 2 * np.pi:
                    raise ValueError(f"Passage {check['id']} endpoint inside {prim.GetPath()}")
            distances.append(segment_surface_distance(check["start"], check["end"], triangles))
        distance = min(distances)
        passed = distance >= check["radius_m"]
        results.append(
            {
                "id": check["id"],
                "representation": check["representation"],
                "clearance_m": distance,
                "required_m": check["radius_m"],
                "status": "pass" if passed else "fail",
            }
        )
        if not passed:
            raise ValueError(
                f"Blocked passage {check['id']}: {distance:g} m < {check['radius_m']:g} m"
            )
    return results
