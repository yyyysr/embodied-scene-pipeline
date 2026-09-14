from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

RUNTIME_ROOT = Path(__file__).resolve().parent.parent
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

from blender_runtime.assets import build_asset
from blender_runtime.cameras import add_review_cameras
from blender_runtime.context import BuildContext
from blender_runtime.lighting import add_review_lighting
from blender_runtime.naming import COLLECTIONS
from blender_runtime.render import render_views
from blender_runtime.script_loader import load_entrypoint
from blender_runtime.validate import validate_scene


def arguments_after_separator() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("scene_spec", type=Path)
    parser.add_argument("--source-workspace", type=Path)
    parser.add_argument("--source-spec", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args(arguments_after_separator())


def reset_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        bpy.data.collections.remove(collection)
    for name in COLLECTIONS:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0


def next_review_directory(output_workspace: Path) -> Path:
    review_root = output_workspace / "review"
    review_root.mkdir(parents=True, exist_ok=True)
    indices = []
    for path in review_root.glob("iteration_*"):
        try:
            indices.append(int(path.name.removeprefix("iteration_")))
        except ValueError:
            continue
    return review_root / f"iteration_{max(indices, default=0) + 1:03d}"


def main() -> None:
    args = parse_args()
    runtime_spec_path = args.scene_spec.resolve()
    spec = json.loads(runtime_spec_path.read_text(encoding="utf-8"))
    source_workspace = (
        args.source_workspace.resolve()
        if args.source_workspace
        else runtime_spec_path.parent.parent
    )
    source_spec_path = args.source_spec.resolve() if args.source_spec else runtime_spec_path
    output_workspace = args.output.resolve() if args.output else source_workspace
    build_directory = output_workspace / "build"
    review_directory = next_review_directory(output_workspace)
    build_directory.mkdir(parents=True, exist_ok=True)
    review_directory.mkdir(parents=True, exist_ok=True)

    reset_scene()
    context = BuildContext(source_workspace, spec)
    implementation = spec.get("implementation", {"mode": "primitive"})
    if implementation["mode"] == "blender_script":
        entrypoint = load_entrypoint(source_workspace, implementation)
        entrypoint(context, spec)
    else:
        for asset in spec.get("objects", []):
            obj = build_asset(asset)
            context.register(
                obj,
                semantic_id=asset["id"],
                role=asset.get("role", "context"),
            )

    structure_contract = context.structure_contract()
    structure_contract_path = build_directory / "structure_contract.json"
    structure_contract_path.write_text(json.dumps(structure_contract, indent=2), encoding="utf-8")
    cameras = add_review_cameras(spec)
    add_review_lighting()
    report = validate_scene(
        spec["id"],
        {asset["id"] for asset in spec.get("objects", [])},
        expected_room_ids={room["id"] for room in spec.get("rooms", [])},
        contract_room_ids=set(structure_contract["rooms"]),
        task_checks=context.review_checks,
    )
    expected_room_ids = [room["id"] for room in spec.get("rooms", [])]
    room_views = {
        room_id: f"room_{room_id}.png"
        for room_id in expected_room_ids
        if f"room_{room_id}" in cameras
    }
    room_inside_views = {
        room_id: f"room_{room_id}_alt.png"
        for room_id in expected_room_ids
        if f"room_{room_id}_alt" in cameras
    }
    report["coverage"] = {
        "required_rooms": expected_room_ids,
        "rendered_rooms": sorted(room_views),
        "room_views": room_views,
        "room_inside_views": room_inside_views,
        "global_views": [view for view in ("overview", "top", "task") if view in cameras],
        "articulation_views": {"representative_open_state": "articulation_open.png"},
    }
    if set(room_views) != set(expected_room_ids):
        report["status"] = "needs_repair"
        report["findings"].append(
            {
                "severity": "blocking",
                "entity_id": "room_review_coverage",
                "message": "One or more resolved rooms has no diagnostic review view.",
                "suggested_fix": "Add a room camera or resolve the missing room polygon.",
            }
        )
    (review_directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    render_views(cameras, review_directory)
    report["artifacts"] = {
        "overview": (review_directory / "overview.png").exists(),
        "top": (review_directory / "top.png").exists(),
        "task": (review_directory / "task.png").exists(),
        "articulation_open": (review_directory / "articulation_open.png").exists(),
        "room_views": {
            room_id: (review_directory / filename).exists()
            for room_id, filename in room_views.items()
        },
        "room_inside_views": {
            room_id: (review_directory / filename).exists()
            for room_id, filename in room_inside_views.items()
        },
    }
    (review_directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(build_directory / "scene.blend"))
    (build_directory / "build_manifest.json").write_text(
        json.dumps(
            {
                "scene_id": spec["id"],
                "scene_spec": str(source_spec_path),
                "source_workspace": str(source_workspace),
                "output_workspace": str(output_workspace),
                "build_mode": implementation["mode"],
                "source_script": implementation.get("script"),
                "structure_contract": str(structure_contract_path),
                "review": str(review_directory),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
