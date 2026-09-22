"""Short-lived native algorithm process. Interchange lives in a temporary directory."""
import json
import sys

import coacd

from .geometry import components
from .validation import summary


def run(data):
    coacd.set_log_level("warn")
    parts, modes = [], []
    for mesh in components(data["vertices"], data["faces"]):
        params = dict(data["parameters"])
        requested = params["preprocess_mode"]
        params["preprocess_mode"] = (
            "off" if mesh.is_volume else "on"
        ) if requested == "auto" else requested
        try:
            result = coacd.run_coacd(coacd.Mesh(mesh.vertices, mesh.faces), **params)
            summary(mesh.vertices, result)
        except Exception as error:
            if requested != "auto" or params["preprocess_mode"] == "on":
                raise
            params["preprocess_mode"] = "on"
            modes.append({"retry_reason": str(error)})
            result = coacd.run_coacd(coacd.Mesh(mesh.vertices, mesh.faces), **params)
        modes.append({"preprocess_mode": params["preprocess_mode"]})
        parts.extend(result)
    info = summary(data["vertices"], parts)
    limit = data["parameters"]["max_convex_hull"]
    if limit != -1 and len(parts) > limit:
        raise ValueError("Total convex parts exceed max_convex_hull across source components")
    info.update(parameters=data["parameters"], components=modes, version="1.0.14")
    return {"parts": [[v.tolist(), f.tolist()] for v, f in parts], "summary": info}


if __name__ == "__main__":
    from pathlib import Path

    data = json.loads(Path(sys.argv[1]).read_text())
    Path(sys.argv[2]).write_text(json.dumps(run(data)))
