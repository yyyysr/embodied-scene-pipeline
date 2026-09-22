import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from .config import resolve
from .geometry import mesh_from_arrays
from .validation import validate_parts


def decompose_mesh(vertices, faces, parameters=None, *, timeout=300):
    mesh = mesh_from_arrays(vertices, faces)
    params = resolve(parameters)
    with tempfile.TemporaryDirectory(prefix="scene_coacd_") as directory:
        source, output = Path(directory) / "input.json", Path(directory) / "output.json"
        source.write_text(json.dumps({"vertices": mesh.vertices.tolist(),
                                     "faces": mesh.faces.tolist(), "parameters": params}))
        env = dict(os.environ)
        env["OMP_NUM_THREADS"] = "1"
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2]) + os.pathsep + env.get(
            "PYTHONPATH", ""
        )
        try:
            result = subprocess.run(
                [sys.executable, "-m", "embodied_scene.collision.worker", str(source), str(output)],
                capture_output=True, text=True, timeout=timeout, env=env, check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise ValueError(f"CoACD exceeded {timeout}s") from error
        if result.returncode or not output.exists():
            raise ValueError(f"CoACD failed ({result.returncode}): {result.stderr[-3000:]}")
        data = json.loads(output.read_text())
        parts = [(np.asarray(v), np.asarray(f, dtype=np.int64)) for v, f in data["parts"]]
        validate_parts(parts)
        return parts, data["summary"]
