import numpy as np

from .geometry import mesh_from_arrays


def validate_parts(parts):
    if not parts:
        raise ValueError("CoACD returned no convex parts")
    meshes = [mesh_from_arrays(v, f) for v, f in parts]
    for mesh in meshes:
        if not mesh.is_volume or not mesh.is_convex:
            raise ValueError("CoACD part must be a closed, positive-volume convex mesh")
    return meshes


def summary(vertices, parts):
    meshes = validate_parts(parts)
    source = np.asarray(vertices)
    points = np.concatenate([m.vertices for m in meshes])
    delta = np.array([points.min(0) - source.min(0), points.max(0) - source.max(0)])
    return {
        "parts": len(parts), "vertices": sum(len(m.vertices) for m in meshes),
        "triangles": sum(len(m.faces) for m in meshes),
        "bounds_delta_m": delta.tolist(),
        "geometry_status": "pass", "task_space_validation": "not_evaluated",
    }
