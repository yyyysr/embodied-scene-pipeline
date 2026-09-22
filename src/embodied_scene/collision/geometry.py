import numpy as np
import trimesh


def mesh_from_arrays(vertices, faces):
    vertices = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(faces)
    if (vertices.ndim != 2 or vertices.shape[1] != 3 or len(vertices) < 4
            or not np.isfinite(vertices).all() or faces.ndim != 2
            or faces.shape[1] != 3 or not len(faces)
            or not np.issubdtype(faces.dtype, np.integer)
            or faces.min() < 0 or faces.max() >= len(vertices)):
        raise ValueError("Collision source requires finite vertices and triangle indices")
    mesh = trimesh.Trimesh(vertices, faces, process=False)
    scale = float(np.ptp(vertices, axis=0).max())
    if scale <= 0 or np.any(mesh.area_faces <= scale * scale * 1e-14):
        raise ValueError("Degenerate collision triangles")
    return mesh


def components(vertices, faces):
    mesh = mesh_from_arrays(vertices, faces)
    # Weld coincident export seams before finding edge-connected components.
    mesh.merge_vertices()
    parts = list(mesh.split(only_watertight=False))
    if not parts:
        raise ValueError("Empty collision source")
    for part in parts:
        mesh_from_arrays(part.vertices, part.faces)
        part.fix_normals()
    return parts
