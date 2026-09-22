"""Versioned CoACD construction policy; distances are meters."""

DEFAULTS = {
    "threshold_m": 0.003, "preprocess_mode": "auto", "max_convex_hull": -1,
    "preprocess_resolution": 50, "resolution": 2000, "seed": 0,
}


def resolve(parameters=None):
    import math

    parameters = parameters or {}
    if set(parameters) - DEFAULTS.keys():
        raise ValueError("Unknown CoACD parameters")
    result = DEFAULTS | parameters
    threshold = result.pop("threshold_m")
    if isinstance(threshold, bool) or not math.isfinite(threshold) or threshold <= 0:
        raise ValueError("threshold_m must be finite and positive")
    if result["preprocess_mode"] not in ("auto", "on", "off"):
        raise ValueError("Invalid preprocess_mode")
    for key in ("max_convex_hull", "preprocess_resolution", "resolution", "seed"):
        value = result[key]
        if type(value) is not int or (value < 1 and not (
            key == "max_convex_hull" and value == -1 or key == "seed" and value == 0
        )):
            raise ValueError(f"Invalid CoACD {key}")
    return result | {
        "threshold": threshold, "real_metric": True, "mcts_nodes": 20,
        "mcts_iterations": 150, "mcts_max_depth": 3, "pca": False,
        "merge": True, "decimate": False, "extrude": False, "apx_mode": "ch",
    }
