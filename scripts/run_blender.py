from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from embodied_scene.specs.validation import validate_specification
from embodied_scene.usd.delivery import export_scene, update_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and review a scene with Blender")
    parser.add_argument("scene", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--geometry-only", action="store_true", help="Explicitly stop after Blender review"
    )
    parser.add_argument("--debug", action="store_true", help="Retain USD interchange files")
    args = parser.parse_args()

    blender = os.environ.get("BLENDER_BIN", "blender")
    executable = shutil.which(blender) if not Path(blender).is_file() else blender
    if not executable:
        raise SystemExit("Blender was not found. Set BLENDER_BIN in your environment.")

    root = Path(__file__).resolve().parents[1]
    scene_path = args.scene.resolve()
    source_workspace = scene_path.parent.parent
    scene_data = validate_specification(scene_path, "scene.schema.json")
    workspace = args.output.resolve() if args.output else source_workspace
    physics_path = scene_path.with_name("physics.yaml")
    if not args.geometry_only:
        try:
            validate_specification(physics_path, "physics.schema.json")
        except Exception as error:  # Report preflight failure before starting Blender.
            update_report(
                workspace,
                {
                    "status": "fail",
                    "errors": [str(error)],
                    "dynamic_validation": {"status": "pending_user"},
                },
            )
            raise SystemExit(f"Physics configuration required before building: {error}") from error
    with tempfile.TemporaryDirectory(prefix="embodied_scene_") as temporary_directory:
        runtime_spec = Path(temporary_directory) / "scene.json"
        runtime_spec.write_text(json.dumps(scene_data), encoding="utf-8")
        command = [
            str(executable),
            "--background",
            "-noaudio",
            "--python-exit-code",
            "1",
            "--python",
            str(root / "blender_runtime" / "build_scene.py"),
            "--",
            str(runtime_spec),
            "--source-workspace",
            str(source_workspace),
            "--source-spec",
            str(scene_path),
        ]
        if args.output:
            command.extend(["--output", str(args.output)])
        try:
            subprocess.run(command, cwd=root, check=True)
        except subprocess.CalledProcessError as error:
            update_report(
                workspace,
                {
                    "status": "fail",
                    "errors": [str(error)],
                    "dynamic_validation": {"status": "pending_user"},
                },
            )
            raise
    review = json.loads((workspace / "review/report.json").read_text())
    if review["status"] != "pass":
        raise SystemExit("Blender checks failed; repair source before USD delivery")
    if not args.geometry_only:
        result = export_scene(
            workspace / "build/scene.blend",
            physics_path,
            workspace,
            debug=args.debug,
            blender=str(executable),
            scene_spec=scene_path,
        )
        if result["status"] != "pass":
            raise SystemExit("USD delivery failed: " + "; ".join(result["errors"]))
        print(f"Delivered {workspace / 'exports/scene.usdc'}; Isaac Sim validation: pending_user")


if __name__ == "__main__":
    main()
