import subprocess

import numpy as np
import pytest
import trimesh

from embodied_scene.collision.coacd import decompose_mesh
from embodied_scene.collision.config import resolve


def test_real_box_and_disconnected_components():
    box = trimesh.creation.box(extents=[0.1, 0.2, 0.3])
    other = box.copy()
    other.apply_translation([0.4, 0, 0])
    source = box + other
    parts, info = decompose_mesh(source.vertices, source.faces)
    assert len(parts) == 2
    assert info["parameters"]["real_metric"] is True
    assert np.allclose(info["bounds_delta_m"], 0, atol=1e-7)
    assert all(c["preprocess_mode"] == "off" for c in info["components"])
    with pytest.raises(ValueError, match="exceed"):
        decompose_mesh(source.vertices, source.faces, {"max_convex_hull": 1})


@pytest.mark.parametrize("params", [
    {"threshold_m": float("nan")}, {"seed": -1}, {"resolution": 0},
    {"max_convex_hull": 0}, {"unknown": 1},
])
def test_bad_settings(params):
    with pytest.raises(ValueError):
        resolve(params)


def test_bad_mesh_and_timeout(monkeypatch):
    box = trimesh.creation.box()
    with pytest.raises(ValueError):
        decompose_mesh(box.vertices, [[0, 0, 0]])

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("coacd", 1)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(ValueError, match="exceeded"):
        decompose_mesh(box.vertices, box.faces, timeout=1)


def test_crash_is_not_silently_replaced(monkeypatch):
    box = trimesh.creation.box()
    monkeypatch.setattr(subprocess, "run", lambda *a, **k:
                        subprocess.CompletedProcess(a, -11, "", "native crash"))
    with pytest.raises(ValueError, match="native crash"):
        decompose_mesh(box.vertices, box.faces)


def test_concave_l_preserves_notch_and_seed():
    outline = np.array([[0, 0], [.1, 0], [.1, .03], [.03, .03], [.03, .1], [0, .1]])
    vertices = np.array([[x, y, z] for z in [0, .02] for x, y in outline])
    cap = [[0, 1, 3], [1, 2, 3], [0, 3, 5], [3, 4, 5]]
    faces = [f[::-1] for f in cap] + [[v+6 for v in f] for f in cap]
    for i in range(6):
        j = (i+1) % 6
        faces.extend([[i, j, j+6], [i, j+6, i+6]])
    parts, _ = decompose_mesh(vertices, faces, {"threshold_m": .001})
    from scipy.spatial import ConvexHull
    sample = np.array([.07, .07, .01])
    assert len(parts) > 1
    for v, _ in parts:
        equations = ConvexHull(v).equations
        assert np.any(equations[:, :3] @ sample + equations[:, 3] > 0)
    repeated, _ = decompose_mesh(vertices, faces, {"threshold_m": .001})
    assert len(repeated) == len(parts)
    assert all(np.allclose(a[0], b[0]) for a, b in zip(parts, repeated))
