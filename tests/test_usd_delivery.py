import json

import pytest
from pxr import Sdf, Usd, UsdGeom, UsdLux

from embodied_scene.usd.delivery import publish_stage, update_report
from embodied_scene.usd.pipeline import validate_usd


def lit_stage(tmp_path):
    stage = Usd.Stage.CreateNew(str(tmp_path / "source.usda"))
    root = UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(root.GetPrim())
    UsdGeom.SetStageMetersPerUnit(stage, 1)
    UsdGeom.SetStageUpAxis(stage, "Z")
    light = UsdLux.DomeLight.Define(stage, "/World/lighting/sky")
    light.CreateIntensityAttr(10)
    (tmp_path / "sky.exr").write_bytes(b"test texture resource")
    light.CreateTextureFileAttr(Sdf.AssetPath("./sky.exr"))
    stage.GetRootLayer().Save()
    return stage


def test_portable_delivery_without_sidecars(tmp_path):
    stage = lit_stage(tmp_path)
    output = tmp_path / "exports"
    result = publish_stage(stage, output)
    assert result["status"] == "pass", result
    assert {p.name for p in output.iterdir()} == {"scene.usdc", "textures"}
    assert not any("sha256" in k for k in result)
    (tmp_path / "sky.exr").unlink()
    moved = tmp_path / "relocated"
    output.rename(moved)
    assert validate_usd(moved / "scene.usdc")["status"] == "pass"
    final = Usd.Stage.Open(str(moved / "scene.usdc"))
    assert not final.GetRootLayer().subLayerPaths
    assert final.GetPrimAtPath("/World/lighting/sky")
    assert (
        UsdLux.DomeLight.Get(final, "/World/lighting/sky")
        .GetTextureFileAttr()
        .Get()
        .path.startswith("./textures/")
    )


def test_failed_publication_preserves_previous_delivery(tmp_path):
    stage = lit_stage(tmp_path)
    output = tmp_path / "exports"
    assert publish_stage(stage, output)["status"] == "pass"
    before = (output / "scene.usdc").read_bytes()
    UsdGeom.SetStageMetersPerUnit(stage, 0.01)
    assert publish_stage(stage, output)["status"] == "fail"
    assert (output / "scene.usdc").read_bytes() == before


def test_unknown_output_not_deleted(tmp_path):
    stage = lit_stage(tmp_path)
    output = tmp_path / "exports"
    output.mkdir()
    (output / "user_notes.txt").write_text("keep")
    with pytest.raises(ValueError, match="unrelated"):
        publish_stage(stage, output)
    assert (output / "user_notes.txt").read_text() == "keep"


def test_single_report_preserves_modeling_findings(tmp_path):
    path = tmp_path / "review/report.json"
    path.parent.mkdir()
    path.write_text(
        json.dumps(
            {
                "scene_id": "demo",
                "status": "needs_repair",
                "checks": {"clearance": False},
                "findings": [{"severity": "major", "message": "Blocked door"}],
            }
        )
    )
    update_report(tmp_path, {"status": "pass", "counts": {"bodies": 2}})
    report = json.loads(path.read_text())
    assert report["status"] == "needs_repair"
    assert report["findings"][0]["message"] == "Blocked door"
    assert report["usd"]["status"] == "pass"
    assert list(path.parent.iterdir()) == [path]
