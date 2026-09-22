"""Configuration, ownership, transaction and output-contract regressions."""

import copy
import json

import jsonschema
import pytest
import yaml
from pxr import Usd, UsdGeom, UsdPhysics

from embodied_scene.config import load_yaml, repository_root
from embodied_scene.integrations.isaacsim.config import (
    load_extension,
    ownership_paths,
    validate_config,
)
from embodied_scene.specs.validation import validate_specification
from embodied_scene.usd.delivery import publish_stage, update_report
from embodied_scene.usd.pipeline import _author


@pytest.fixture
def config():
    return load_yaml(repository_root() / "templates/isaacsim.yaml")


def test_template_is_schema_valid():
    path = repository_root() / "templates/isaacsim.yaml"
    validate_config(validate_specification(path, "isaacsim.schema.json"))


@pytest.mark.parametrize(
    "change,match",
    [
        (lambda c: c["deformables"].append(copy.deepcopy(c["deformables"][0])), "Duplicate"),
        (lambda c: c["materials"]["soft_sample"].update(youngs_modulus_pa=float("nan")), "finite"),
        (lambda c: c["deformables"][0].update(material="absent"), "Unknown"),
        (lambda c: c["materials"]["soft_sample"].pop("density_kg_m3"), "mass_kg"),
        (lambda c: c["deformables"][0].update(kind="surface"), "thickness"),
        (lambda c: c["deformables"][0]["contact"].update(rest_offset_m=0.02), "exceed"),
        (
            lambda c: c["deformables"][0]["contact"].update(
                self_collision_filter_distance_m=0.0001
            ),
            "filter distance",
        ),
        (
            lambda c: c["deformables"][0]["solver"].update(collision_pair_update_frequency=100),
            "frequency",
        ),
        (
            lambda c: c["deformables"][0]["solver"].update(collision_iteration_multiplier=9),
            "multiplier",
        ),
        (
            lambda c: c["deformables"][0]["solver"].update(max_linear_velocity_m_s="auto"),
            "Surface-only",
        ),
    ],
)
def test_semantic_rejections(config, change, match):
    change(config)
    with pytest.raises(ValueError, match=match):
        validate_config(config)


def test_unknown_unsupported_parameter_is_not_silently_written(config, tmp_path):
    config["materials"]["soft_sample"]["static_friction"] = 0.5
    path = tmp_path / "isaacsim.yaml"
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(jsonschema.ValidationError):
        validate_specification(path, "isaacsim.schema.json")


def geometry(tmp_path):
    stage = Usd.Stage.CreateNew(str(tmp_path / "geometry.usdc"))
    stage.SetDefaultPrim(UsdGeom.Xform.Define(stage, "/World").GetPrim())
    UsdGeom.SetStageUpAxis(stage, "Z")
    UsdGeom.SetStageMetersPerUnit(stage, 1)
    UsdGeom.Xform.Define(stage, "/World/soft_object")
    mesh = UsdGeom.Mesh.Define(stage, "/World/soft_object/soft_object_surface")
    mesh.CreatePointsAttr([(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)])
    mesh.CreateFaceVertexCountsAttr([3] * 4)
    mesh.CreateFaceVertexIndicesAttr([0, 2, 1, 0, 1, 3, 0, 3, 2, 1, 2, 3])
    stage.GetRootLayer().Save()
    return stage


def physics():
    return {
        "version": 1,
        "materials": {
            "default": {"static_friction": 0.5, "dynamic_friction": 0.5, "restitution": 0}
        },
        "default_material": "default",
        "bodies": [],
        "joints": [],
    }


def mapping():
    return {
        "soft_object": "/World/soft_object",
        "soft_object_surface": "/World/soft_object/soft_object_surface",
    }


def test_extension_is_explicit_and_confined(config, tmp_path):
    path = tmp_path / "physics.yaml"
    data = physics()
    path.write_text(yaml.safe_dump(data))
    assert load_extension(path) is None
    data["extensions"] = {"isaacsim": "../outside.yaml"}
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="inside specs"):
        load_extension(path)
    data["extensions"]["isaacsim"] = "isaacsim.yaml"
    path.write_text(yaml.safe_dump(data))
    (tmp_path / "isaacsim.yaml").write_text(yaml.safe_dump(config))
    assert load_extension(path) == config


def test_soft_geometry_is_owned_not_visual_only(config, tmp_path):
    geometry(tmp_path)
    with pytest.raises(ValueError, match="Unclassified"):
        _author(physics(), tmp_path, mapping())
    stage = _author(physics(), tmp_path, mapping(), extension=config)
    assert not stage.GetPrimAtPath("/World/soft_object").HasAPI(UsdPhysics.RigidBodyAPI)
    duplicate = physics()
    duplicate["visual_only"] = ["soft_object"]
    with pytest.raises(ValueError, match="Overlapping"):
        _author(duplicate, tmp_path, mapping(), extension=config)


def test_overlapping_soft_roots_rejected(config, tmp_path):
    stage = geometry(tmp_path)
    UsdGeom.Xform.Define(stage, "/World/soft_object/nested")
    other = copy.deepcopy(config["deformables"][0])
    other.update(id="other", object="other")
    config["deformables"].append(other)
    with pytest.raises(ValueError, match="Overlapping"):
        ownership_paths(config, stage, {**mapping(), "other": "/World/soft_object/nested"})


@pytest.mark.parametrize("raises", [False, True])
def test_extension_failure_does_not_publish(tmp_path, raises):
    stage = geometry(tmp_path)
    out = tmp_path / "exports"
    assert publish_stage(stage, out)["status"] == "pass"
    before = (out / "scene.usdc").read_bytes()

    def reject(path):
        assert path.is_file()
        if raises:
            raise RuntimeError("worker failed")
        return {"status": "fail", "errors": ["missing tetmesh"]}

    if raises:
        with pytest.raises(RuntimeError):
            publish_stage(stage, out, validate_extension=reject)
    else:
        assert publish_stage(stage, out, validate_extension=reject)["status"] == "fail"
    assert (out / "scene.usdc").read_bytes() == before
    assert {p.name for p in out.iterdir()} == {"scene.usdc"}
    assert not list(tmp_path.glob(".usd_delivery_*"))


def test_reexport_invalidates_but_retains_previous_user_evidence(tmp_path):
    update_report(
        tmp_path,
        {"status": "pass", "dynamic_validation": {"status": "pass", "evidence": "user-test"}},
    )
    update_report(tmp_path, {"status": "pass", "dynamic_validation": {"status": "pending_user"}})
    report = json.loads((tmp_path / "review/report.json").read_text())
    dynamic = report["usd"]["dynamic_validation"]
    assert dynamic["status"] == "pending_user"
    assert dynamic["previous_evidence"]["evidence"] == "user-test"
    assert {p.name for p in (tmp_path / "review").iterdir()} == {"report.json"}


@pytest.mark.parametrize("hex_resolution", [None, 6])
def test_offline_volume_roundtrip(config, tmp_path, monkeypatch, hex_resolution):
    from embodied_scene.integrations.isaacsim.schema import has_api
    from embodied_scene.integrations.isaacsim.validation import validate_file

    monkeypatch.delenv("ISAACSIM_PYTHON", raising=False)
    if hex_resolution:
        config["deformables"][0]["cooking"] = {"volume_hex_resolution": hex_resolution}
    geometry(tmp_path)
    stage = _author(physics(), tmp_path, mapping(), extension=config)
    out = tmp_path / "exports"
    result = publish_stage(
        stage, out, validate_extension=lambda p: validate_file(p, config, mapping())
    )
    assert result["status"] == "pass"
    assert result["isaacsim"]["volume_mesh_generation"] == "deferred"
    saved = Usd.Stage.Open(str(out / "scene.usdc"))
    root = saved.GetPrimAtPath(mapping()["soft_object"])
    assert has_api(root, "PhysxAutoDeformableBodyAPI")
    sim = saved.GetPrimAtPath(root.GetPath().AppendChild("SimulationMesh"))
    assert sim.GetTypeName() == "TetMesh"
    assert sim.GetAttribute("points").Get() is None
    assert {p.name for p in out.iterdir()} == {"scene.usdc"}
    root.GetRelationship("physxDeformableBody:cookingSourceMesh").ClearTargets(True)
    saved.GetRootLayer().Save()
    with pytest.raises(ValueError, match="cooking source"):
        validate_file(out / "scene.usdc", config, mapping())


def test_surface_attachment_roundtrip(config, tmp_path):
    from embodied_scene.integrations.isaacsim.validation import validate_file

    config["deformables"][0]["kind"] = "surface"
    config["materials"]["soft_sample"].update(
        surface_thickness_m=0.001, bend_stiffness_pa="isotropic_shell"
    )
    config["attachments"] = [
        {
            "id": "pin",
            "body": "soft_object",
            "target": "anchor",
            "region": {"frame": "body_local", "min": [-0.01] * 3, "max": [0.01] * 3},
        }
    ]
    stage = geometry(tmp_path)
    UsdGeom.Xform.Define(stage, "/World/anchor").AddTranslateOp().Set((2, 3, 4))
    stage.GetRootLayer().Save()
    refs = {**mapping(), "anchor": "/World/anchor"}
    stage = _author(physics(), tmp_path, refs, extension=config)
    result = publish_stage(
        stage, tmp_path / "exports", validate_extension=lambda p: validate_file(p, config, refs)
    )
    assert result["status"] == "pass"
    assert result["isaacsim"]["counts"] == {"volume": 0, "surface": 1, "attachments": 1}


def test_volume_node_state_requires_known_topology(config):
    config["deformables"][0]["initial_velocity_m_s"] = [1, 0, 0]
    with pytest.raises(ValueError, match="zero initial velocity"):
        validate_config(config)
    config["deformables"][0].pop("initial_velocity_m_s")
    config["attachments"] = [
        {
            "id": "pin",
            "body": "soft_object",
            "target": "anchor",
            "region": {"frame": "body_local", "min": [0, 0, 0], "max": [1, 1, 1]},
        }
    ]
    with pytest.raises(ValueError, match="surface simulation"):
        validate_config(config)


def test_shared_export_uses_only_blender_subprocess(config, tmp_path, monkeypatch):
    from embodied_scene.usd import delivery

    monkeypatch.delenv("ISAACSIM_PYTHON", raising=False)
    blend = tmp_path / "scene.blend"
    blend.write_bytes(b"fixture")
    spec = physics()
    spec["extensions"] = {"isaacsim": "isaacsim.yaml"}
    p = tmp_path / "physics.yaml"
    p.write_text(yaml.safe_dump(spec))
    (tmp_path / "isaacsim.yaml").write_text(yaml.safe_dump(config))
    calls = []

    def export(command, **kwargs):
        calls.append(command)
        assert command[0] == "/fake/blender"
        from pathlib import Path

        exchange = Path(command[-1])
        geometry(exchange)

    monkeypatch.setattr(delivery.shutil, "which", lambda value: "/fake/blender")
    monkeypatch.setattr(delivery.subprocess, "run", export)
    monkeypatch.setattr(delivery, "build_object_map", lambda *a, **k: {"objects": mapping()})
    result = delivery.export_scene(blend, p, tmp_path)
    assert result["status"] == "pass", result
    assert result["isaacsim"]["authoring"] == "offline"
    assert len(calls) == 1
    assert {p.name for p in (tmp_path / "exports").iterdir()} == {"scene.usdc"}


@pytest.mark.parametrize("damage", ["bind", "material", "api", "offset"])
def test_corrupt_declarations_fail_before_replacement(config, tmp_path, damage):
    from embodied_scene.integrations.isaacsim.validation import validate_file

    geometry(tmp_path)
    stage = _author(physics(), tmp_path, mapping(), extension=config)
    out = tmp_path / "exports"
    validator = lambda p: validate_file(p, config, mapping())
    assert publish_stage(stage, out, validate_extension=validator)["status"] == "pass"
    before = (out / "scene.usdc").read_bytes()
    root = stage.GetPrimAtPath(mapping()["soft_object"])
    if damage == "bind":
        stage.GetPrimAtPath(mapping()["soft_object_surface"]).GetAttribute(
            "deformablePose:default:omniphysics:points"
        ).Set([(0, 0, 0)])
    elif damage == "material":
        root.GetRelationship("material:binding:physics").SetTargets(["/absent"])
    elif damage == "api":
        root.RemoveAppliedSchema("PhysxAutoDeformableBodyAPI")
    else:
        stage.GetPrimAtPath(root.GetPath().AppendChild("SimulationMesh")).GetAttribute(
            "physxCollision:contactOffset"
        ).Set(0.1)
    try:
        result = publish_stage(stage, out, validate_extension=validator)
        assert result["status"] == "fail"
    except ValueError:
        pass
    assert (out / "scene.usdc").read_bytes() == before
