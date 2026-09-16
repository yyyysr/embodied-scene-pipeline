"""One final USD and its resources; all interchange files are temporary by default."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from pxr import UsdUtils

from embodied_scene.config import repository_root
from embodied_scene.usd.pipeline import author_stage, build_object_map, validate_usd, write_json


def update_report(workspace: Path, result: dict) -> None:
    path = workspace / "review/report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    report = (
        json.loads(path.read_text())
        if path.exists()
        else {
            "scene_id": workspace.name,
            "status": "pass",
            "checks": {},
            "findings": [],
        }
    )
    report["usd"] = result
    report["checks"]["usd"] = result["status"] == "pass"
    report["status"] = (
        "pass"
        if all(report["checks"].values())
        and not any(f["severity"] in ("blocking", "major") for f in report["findings"])
        else "needs_repair"
    )
    write_json(path, report)


def flatten_with_assets(stage, directory: Path) -> Path:
    """Flatten composition without flattening object hierarchy; localize resources."""
    directory.mkdir(parents=True, exist_ok=True)
    layer = stage.Flatten()
    copied = {}
    used_names = set()

    def localize(asset):
        if not asset:
            return asset
        if asset in copied:
            return copied[asset]
        source = Path(asset)
        # Flatten resolves authored relative assets against their original layer.
        if not source.is_absolute():
            raise ValueError(f"Asset did not resolve to a local path: {asset}")
        files = sorted(source.parent.glob(source.name.replace("<UDIM>", "[0-9][0-9][0-9][0-9]")))
        if not files or any(not p.is_file() for p in files):
            raise ValueError(f"Missing asset: {asset}")
        name = source.name
        index = 1
        while name in used_names:
            name = f"{index}_{source.name}"
            index += 1
        used_names.add(name)
        texture_dir = directory / "textures"
        texture_dir.mkdir(exist_ok=True)
        for file in files:
            target_name = name.replace("<UDIM>", file.stem[-4:]) if "<UDIM>" in name else name
            target = texture_dir / target_name
            if target.exists():
                raise ValueError(f"Resource name collision: {target_name}")
            shutil.copy2(file, target)
        copied[asset] = "./textures/" + name
        return copied[asset]

    UsdUtils.ModifyAssetPaths(layer, localize)
    path = directory / "scene.usdc"
    if not layer.Export(str(path)):
        raise ValueError("USD export failed")
    return path


def publish_stage(stage, output: Path) -> dict:
    """Validate staged output before replacing a previous managed delivery."""
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    unexpected = (
        {p.name for p in output.iterdir()} - {"scene.usdc", "textures"}
        if output.exists()
        else set()
    )
    if unexpected:
        raise ValueError(
            "Output contains legacy or unrelated files; move them out first: "
            + ", ".join(sorted(unexpected))
        )
    with tempfile.TemporaryDirectory(prefix=".usd_delivery_", dir=output.parent) as temporary:
        temporary = Path(temporary)
        candidate = temporary / "new"
        path = flatten_with_assets(stage, candidate)
        result = validate_usd(path)
        if result["status"] != "pass":
            return result
        previous = temporary / "previous"
        if output.exists():
            os.replace(output, previous)
        try:
            os.replace(candidate, output)
        except OSError:
            if previous.exists():
                os.replace(previous, output)
            raise
    return result


def export_scene(
    blend: Path, physics: Path, workspace: Path, *, debug=False, blender: str | None = None,
    configure_stage=None, scene_spec: Path | None = None
) -> dict:
    workspace = workspace.resolve()
    try:
        if not blend.is_file():
            raise ValueError(f"Missing Blender scene: {blend}")
        if not physics.is_file():
            raise ValueError(f"Missing physics configuration: {physics}")
        executable = shutil.which(blender or os.environ.get("BLENDER_BIN", "blender"))
        if not executable:
            raise ValueError("Blender not found; set BLENDER_BIN")
        with tempfile.TemporaryDirectory(prefix="scene_export_") as temporary:
            exchange = Path(temporary)
            subprocess.run(
                [
                    executable,
                    "--background",
                    "-noaudio",
                    str(blend.resolve()),
                    "--python-exit-code",
                    "1",
                    "--python",
                    str(repository_root() / "blender_runtime/export_usd.py"),
                    "--",
                    str(exchange),
                ],
                check=True,
            )
            try:
                mapping = build_object_map(exchange, debug=debug)["objects"]
                stage = author_stage(physics, exchange, mapping, debug=debug)
                from embodied_scene.assembly import compose_background
                from embodied_scene.specs.validation import validate_specification

                specification = scene_spec or workspace / "specs/scene.yaml"
                if specification.exists():
                    spec = validate_specification(specification, "scene.schema.json")
                    compose_background(stage, spec, specification.resolve().parents[1], exchange)
                if configure_stage is not None:
                    configure_stage(stage)
                result = publish_stage(stage, workspace / "exports")
            finally:
                if debug:
                    destination = workspace / "build/usd_debug"
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if destination.exists():
                        shutil.rmtree(destination)
                    shutil.copytree(exchange, destination)
    except Exception as error:  # noqa: BLE001 - report boundary; never publish unchecked output
        result = {
            "status": "fail",
            "errors": [str(error)],
            "dynamic_validation": {"status": "pending_user", "simulator": "Isaac Sim"},
        }
    update_report(workspace, result)
    return result
