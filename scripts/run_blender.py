from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and review a scene with Blender")
    parser.add_argument("scene", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    blender = os.environ.get("BLENDER_BIN", "blender")
    executable = shutil.which(blender) if not Path(blender).is_file() else blender
    if not executable:
        raise SystemExit("Blender was not found. Set BLENDER_BIN in your environment.")

    root = Path(__file__).resolve().parents[1]
    scene_path = args.scene.resolve()
    source_workspace = scene_path.parent.parent
    scene_data = yaml.safe_load(scene_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="embodied_scene_") as temporary_directory:
        runtime_spec = Path(temporary_directory) / "scene.json"
        runtime_spec.write_text(json.dumps(scene_data), encoding="utf-8")
        command = [
            str(executable),
            "--background",
            "-noaudio",
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
        subprocess.run(command, cwd=root, check=True)


if __name__ == "__main__":
    main()
