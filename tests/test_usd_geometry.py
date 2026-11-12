import io

import numpy as np
import pytest
import trimesh
from pxr import Usd, UsdGeom, UsdPhysics

from embodied_scene.usd.geometry import (
    compare_triangles,
    mesh_triangles,
    segment_surface_distance,
    validate_passages,
    validate_surfaces,
)


def mesh_stage(vertices, faces):
    stage = Usd.Stage.CreateInMemory()
    mesh = UsdGeom.Mesh.Define(stage, "/World/plate")
    mesh.CreatePointsAttr(vertices)
    mesh.CreateFaceVertexCountsAttr([3] * len(faces))
    mesh.CreateFaceVertexIndicesAttr(np.asarray(faces).reshape(-1).tolist())
    mesh.CreateSubdivisionSchemeAttr("none")
    return stage, mesh


def test_fidelity_accepts_reordering_and_float32_roundoff():
    surface = np.array(
        [[[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 0, 0], [0, 1, 0], [0, 0, 1]]], dtype=float
    )
    compare_triangles(surface, surface[::-1, ::-1] + 1e-7)
    with pytest.raises(ValueError, match="count"):
        compare_triangles(surface, surface[:1])
    # Identical bounds, different connectivity/surface.
    changed = surface.copy()
    changed[1, 0] = [1, 0, 0]
    with pytest.raises(ValueError, match="surface"):
        compare_triangles(surface, changed)
    with pytest.raises(ValueError, match="surface"):
        compare_triangles(surface, np.repeat(surface[:1], 2, axis=0))


def test_final_stage_surface_changes_are_rejected():
    stage, mesh = mesh_stage([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [[0, 1, 2]])
    buffer = io.BytesIO()
    np.savez(buffer, surface_plate=mesh_triangles(mesh.GetPrim()))
    buffer.seek(0)
    with np.load(buffer) as reference:
        assert validate_surfaces(stage, reference)["meshes"] == 1
        mesh.CreateSubdivisionSchemeAttr("catmullClark")
        with pytest.raises(ValueError, match="subdivision"):
            validate_surfaces(stage, reference)
        mesh.CreateSubdivisionSchemeAttr("none")
        mesh.CreatePointsAttr([(0, 0, 0)] * 3)
        with pytest.raises(ValueError, match="Degenerate"):
            validate_surfaces(stage, reference)


def test_segment_distance_interior_edges_endpoints_and_parallel():
    triangles = np.array([[[0, 0, 0], [1, 0, 0], [0, 1, 0]]], dtype=float)
    assert segment_surface_distance([0.2, 0.2, -1], [0.2, 0.2, 1], triangles) == 0
    assert segment_surface_distance([0.2, 0.2, 1], [0.2, 0.2, 2], triangles) == pytest.approx(1)
    assert segment_surface_distance([0.2, 0.2, 1], [0.4, 0.2, 1], triangles) == pytest.approx(1)
    assert segment_surface_distance([0.5, -1, -1], [0.5, -1, 1], triangles) == pytest.approx(1)
    # Coplanar path crosses the triangle edges.
    assert segment_surface_distance([-0.5, 0.2, 0], [1.5, 0.2, 0], triangles) == pytest.approx(0)
    with pytest.raises(ValueError, match="differ"):
        segment_surface_distance([0, 0, 1], [0, 0, 1], triangles)


def test_passage_rejects_radius_intrusion_and_interior_endpoints():
    box = trimesh.creation.box(extents=[1, 1, 1])
    stage, mesh = mesh_stage(box.vertices.tolist(), box.faces.tolist())
    mapping = {"plate": str(mesh.GetPath())}
    check = {
        "id": "opening",
        "objects": ["plate"],
        "representation": "visual",
        "start": [0.7, 0, -1],
        "end": [0.7, 0, 1],
        "radius_m": 0.1,
    }
    assert validate_passages(stage, [check], mapping)[0]["status"] == "pass"
    # Center line clears the box but the required radius does not.
    check["radius_m"] = 0.3
    with pytest.raises(ValueError, match="Blocked passage"):
        validate_passages(stage, [check], mapping)
    check.update(start=[0, 0, 0], end=[0, 0, 0.1], radius_m=0.01)
    with pytest.raises(ValueError, match="endpoint inside"):
        validate_passages(stage, [check], mapping)
    check.update(start=[0.7, 0, -1], end=[0.7, 0, 1], representation="collision")
    UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
    UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim()).CreateApproximationAttr("convexDecomposition")
    with pytest.raises(ValueError, match="Cannot certify cooked collider"):
        validate_passages(stage, [check], mapping)


def test_passage_uses_convex_collision_hull_not_visual_cavity():
    # Four strips forming a square ring: the visual hole is open, the single hull closes it.
    parts = []
    for center, extents in [
        ([0, -0.75, 0], [2, 0.5, 0.1]),
        ([0, 0.75, 0], [2, 0.5, 0.1]),
        ([-0.75, 0, 0], [0.5, 1, 0.1]),
        ([0.75, 0, 0], [0.5, 1, 0.1]),
    ]:
        part = trimesh.creation.box(extents=extents)
        part.apply_translation(center)
        parts.append(part)
    ring = trimesh.util.concatenate(parts)
    stage, mesh = mesh_stage(ring.vertices.tolist(), ring.faces.tolist())
    check = {
        "id": "ring",
        "objects": ["plate"],
        "representation": "visual",
        "start": [0, 0, -1],
        "end": [0, 0, 1],
        "radius_m": 0.2,
    }
    mapping = {"plate": str(mesh.GetPath())}
    assert validate_passages(stage, [check], mapping)[0]["status"] == "pass"
    UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
    UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim()).CreateApproximationAttr("convexHull")
    check["representation"] = "collision"
    with pytest.raises(ValueError, match="Blocked passage"):
        validate_passages(stage, [check], mapping)
