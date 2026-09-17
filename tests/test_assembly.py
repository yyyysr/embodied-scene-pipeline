import gzip
import math
import struct

import pytest
from pxr import Gf, Usd, UsdGeom

from embodied_scene.assembly import (
    compose_background,
    default_assembly,
    validate_assembly,
    workspace_asset,
)
from embodied_scene.usd.delivery import publish_stage
from embodied_scene.usd.pipeline import validate_usd


def small_spz():
    """One asymmetric Gaussian: source center (1,2,3), nonidentity orientation."""
    header = struct.pack("<IIIBBBB", 0x5053474E, 3, 1, 0, 12, 0, 0)
    position = b"".join((v * 4096).to_bytes(3, "little", signed=True) for v in (1, 2, 3))
    return gzip.compress(
        header
        + position
        + bytes([200, 128, 128, 128, 144, 152, 160])
        + struct.pack("<I", (3 << 30) | 181)
    )


@pytest.mark.parametrize("source_sign, expected", [(1, (7, 6, 8)), (-1, (1, 6, 4))])
def test_composed_gaussian_is_portable_and_matches_editor_coordinates(tmp_path, source_sign, expected):
    source = tmp_path / "background.spz"
    source.write_bytes(small_spz())
    assembly = default_assembly()
    s = math.sqrt(0.5)
    assembly["background"]["source_to_world"] = {
        "orientation_xyzw": [source_sign * s, 0, 0, s],
        "meters_per_source_unit": 0.5,
    }
    assembly["background"]["placement"] = {
        "position_m": [4, 5, 6],
        "orientation_xyzw": [0, 0, s, s],
        "uniform_scale": 2,
    }
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(root.GetPrim())
    UsdGeom.SetStageUpAxis(stage, "Z")
    UsdGeom.SetStageMetersPerUnit(stage, 1)
    compose_background(
        stage,
        {
            "assembly": assembly,
            "world": {"background_mode": "3dgs", "background_asset": source.name},
        },
        tmp_path,
        tmp_path,
    )
    assert publish_stage(stage, tmp_path / "exports")["status"] == "pass"
    source.unlink()
    (tmp_path / "background.usdc").unlink()
    final = Usd.Stage.Open(str(tmp_path / "exports/scene.usdc"))
    splat = final.GetPrimAtPath("/World/BackgroundPlacement/SourceToWorld/Splat")
    matrix = UsdGeom.XformCache().GetLocalToWorldTransform(splat)
    point = matrix.Transform(Gf.Vec3d(*splat.GetAttribute("positions").Get()[0]))
    assert tuple(point) == pytest.approx(expected)
    assert tuple(splat.GetAttribute("positions").Get()[0]) == (1, 2, 3)
    orientation = splat.GetAttribute("orientations").Get()[0]
    assert orientation.GetImaginary()[2] == pytest.approx(181 * math.sqrt(0.5) / 511)
    assert not splat.HasAuthoredReferences()
    assert list((tmp_path / "exports").iterdir()) == [tmp_path / "exports/scene.usdc"]
    assert validate_usd(tmp_path / "exports/scene.usdc")["status"] == "pass"
    splat.GetAttribute("scales").Set([Gf.Vec3f(-1, 1, 1)])
    final.GetRootLayer().Save()
    assert validate_usd(tmp_path / "exports/scene.usdc")["status"] == "fail"


@pytest.mark.parametrize("q", [[0, 0, 0, 0], [0, 0, 0, 2], [float("nan"), 0, 0, 1]])
def test_invalid_orientation_rejected(q):
    assembly = default_assembly()
    assembly["background"]["placement"]["orientation_xyzw"] = q
    with pytest.raises(ValueError):
        validate_assembly(assembly)


def test_asset_cannot_escape_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.spz"
    outside.touch()
    (workspace / "link.spz").symlink_to(outside)
    for path in ("../outside.spz", "link.spz", str(outside)):
        with pytest.raises(ValueError):
            workspace_asset(workspace, path)
