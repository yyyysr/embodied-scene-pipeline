"""Shared meter/Z-up placement contract for the editor and USD publisher."""

import math
from pathlib import Path

from pxr import Gf, UsdGeom

IDENTITY = [0, 0, 0, 1]  # xyzw, also used by Three.js


def default_assembly():
    return {
        "version": 1,
        "background": {
            "source_to_world": {
                "orientation_xyzw": IDENTITY.copy(),
                "meters_per_source_unit": 1,
            },
            "placement": {
                "position_m": [0, 0, 0],
                "orientation_xyzw": IDENTITY.copy(),
                "uniform_scale": 1,
            },
        },
    }


def workspace_asset(workspace: Path, relative: str) -> Path:
    root = workspace.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"Missing or out-of-workspace asset: {relative}")
    return path


def validate_assembly(assembly):
    """Schema handles shape; enforce finite values and unit quaternions as well."""
    import json

    import jsonschema

    from embodied_scene.config import repository_root

    schema = json.loads((repository_root() / "schemas/assembly.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(assembly)
    background = assembly["background"]
    for transform in (background["source_to_world"], background["placement"]):
        q = transform["orientation_xyzw"]
        values = [
            v
            for value in transform.values()
            for v in (value if isinstance(value, list) else [value])
        ]
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Transform values must be finite")
        if abs(sum(v * v for v in q) - 1) > 1e-5:
            raise ValueError("orientation_xyzw must be a unit quaternion")
    return assembly


def author_transform(stage, path, *, orientation_xyzw, position_m=(0, 0, 0), scale=1):
    """USD ops implement T R S; do not copy Three.js matrix storage into Gf."""
    node = UsdGeom.Xform.Define(stage, path)
    node.AddTranslateOp().Set(Gf.Vec3d(*position_m))
    x, y, z, w = orientation_xyzw
    node.AddOrientOp(UsdGeom.XformOp.PrecisionDouble).Set(Gf.Quatd(w, x, y, z))
    node.AddScaleOp().Set(Gf.Vec3f(scale, scale, scale))
    return node


def compose_background(stage, spec, workspace: Path, temporary: Path):
    assembly = spec.get("assembly")
    if assembly is None:
        return
    validate_assembly(assembly)
    if spec.get("world", {}).get("background_mode") != "3dgs":
        raise ValueError("Background assembly requires world.background_mode: 3dgs")
    from usd_convert_gsplat import read_spz, write_gaussian_splat_usd

    source = workspace_asset(workspace, spec["world"]["background_asset"])
    converted = temporary / "background.usdc"
    # Keep all source-local data, including SH, intact. Parent Xforms perform alignment.
    write_gaussian_splat_usd(read_spz(str(source)), str(converted), prim_name="Splat", up_axis="Z")
    root = str(stage.GetDefaultPrim().GetPath()) + "/BackgroundPlacement"
    if stage.GetPrimAtPath(root):
        raise ValueError(f"Reserved assembly path already exists: {root}")
    bg = assembly["background"]
    p = bg["placement"]
    author_transform(
        stage,
        root,
        orientation_xyzw=p["orientation_xyzw"],
        position_m=p["position_m"],
        scale=p["uniform_scale"],
    )
    c = bg["source_to_world"]
    author_transform(
        stage,
        root + "/SourceToWorld",
        orientation_xyzw=c["orientation_xyzw"],
        scale=c["meters_per_source_unit"],
    )
    stage.DefinePrim(root + "/SourceToWorld/Splat").GetReferences().AddReference(
        str(converted), "/Splat"
    )


def validate_splats(prim):
    """Validate authored Gaussian arrays without requiring a renderer/plugin."""
    import numpy as np

    errors = []
    count = len(prim.GetAttribute("positions").Get() or [])
    for name in ("positions", "scales", "opacities", "orientations"):
        value = prim.GetAttribute(name).Get()
        if value is None or len(value) != count or count == 0:
            errors.append(f"Invalid Gaussian {name} count: {prim.GetPath()}")
            continue
        if name == "orientations":
            array = np.array([[q.GetReal(), *q.GetImaginary()] for q in value])
            valid = np.isfinite(array).all() and np.allclose(
                np.linalg.norm(array, axis=1), 1, atol=1e-3
            )
        else:
            array = np.asarray(value)
            valid = np.isfinite(array).all()
            if name == "scales":
                valid = valid and (array > 0).all()
            if name == "opacities":
                valid = valid and ((array >= 0) & (array <= 1)).all()
        if not valid:
            errors.append(f"Invalid Gaussian {name}: {prim.GetPath()}")
    degree = prim.GetAttribute("radiance:sphericalHarmonicsDegree").Get()
    sh = prim.GetAttribute("radiance:sphericalHarmonicsCoefficients").Get()
    if degree is None or sh is None or len(sh) != count * (degree + 1) ** 2:
        errors.append(f"Invalid Gaussian SH count: {prim.GetPath()}")
    elif not np.isfinite(np.asarray(sh)).all():
        errors.append(f"Non-finite Gaussian SH: {prim.GetPath()}")
    matrix = UsdGeom.XformCache().GetLocalToWorldTransform(prim)
    if not all(math.isfinite(v) for row in matrix for v in row) or matrix.GetDeterminant() <= 0:
        errors.append(f"Invalid Gaussian world transform: {prim.GetPath()}")
    return errors
