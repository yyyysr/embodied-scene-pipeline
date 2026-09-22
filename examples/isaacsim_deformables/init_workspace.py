"""Create editable example inputs; run the normal build/export entry point afterwards."""

import argparse
import shutil
from pathlib import Path

import yaml

from embodied_scene.config import load_yaml, repository_root
from embodied_scene.integrations.isaacsim.config import load_extension
from embodied_scene.project import create_workspace
from embodied_scene.specs.validation import validate_specification


def create(name, kind, profile):
    workspace = create_workspace(name)
    shutil.copy2(Path(__file__).with_name("scene.py"), workspace / "source/build_scene.py")
    (workspace / "input/prompt.md").write_text(
        f"Create the repository {kind} deformable construction example. "
        "Material values are uncalibrated; user performs dynamic acceptance.\n"
    )
    surface = kind == "hanging_cloth"
    scene = {
        "id": name,
        "environment": "tabletop",
        "description": kind,
        "implementation": {
            "mode": "blender_script",
            "script": "source/build_scene.py",
            "entrypoint": "build_scene",
        },
        "objects": [
            {"id": "floor", "role": "structure"},
            {
                "id": "soft_object",
                "role": "task",
                "dimensions": [0.5, 0.5, 0.001] if surface else [0.2] * 3,
                "position": [0, 0, 0.6],
            },
        ],
    }
    if surface:
        scene["objects"].append({"id": "cloth_anchor", "role": "context"})
    physics = {
        "version": 1,
        "extensions": {"isaacsim": "isaacsim.yaml"},
        "materials": {
            "default": {"static_friction": 0.5, "dynamic_friction": 0.5, "restitution": 0}
        },
        "default_material": "default",
        "bodies": [
            {
                "id": "floor",
                "object": "floor",
                "type": "static",
                "colliders": [{"object": "floor", "approximation": "none"}],
            }
        ],
        "joints": [],
    }
    extension = load_yaml(repository_root() / "templates/isaacsim.yaml")
    extension["runtime"]["profile"] = profile
    body = extension["deformables"][0]
    if surface:
        body["kind"] = "surface"
        body["rest_bend"] = "flatDefault"
        body["contact"]["self_collision"] = True
        extension["materials"]["soft_sample"].update(
            {
                "youngs_modulus_pa": 1000000,
                "poissons_ratio": 0.3,
                "density_kg_m3": 300,
                "surface_thickness_m": 0.001,
                "bend_stiffness_pa": "isotropic_shell",
                "source": "Uncalibrated isotropic shell demonstration; not measured fabric",
            }
        )
        for label, x in (("left", -0.25), ("right", 0.25)):
            extension["attachments"].append(
                {
                    "id": label,
                    "body": "soft_object",
                    "target": "cloth_anchor",
                    "region": {
                        "frame": "body_local",
                        "min": [x - 0.01, 0.24, -0.01],
                        "max": [x + 0.01, 0.26, 0.01],
                    },
                }
            )
    else:
        body["cooking"] = {"volume_hex_resolution": 6}
    task = load_yaml(workspace / "specs/task.yaml")
    task.update(
        {
            "id": name,
            "manipulated_objects": ["soft_object"],
            "goal": "Inspect soft-body construction; robot interaction and dynamics await user validation.",
        }
    )
    for filename, data in (
        ("scene", scene),
        ("physics", physics),
        ("isaacsim", extension),
        ("task", task),
    ):
        path = workspace / "specs" / (filename + ".yaml")
        path.write_text(yaml.safe_dump(data, sort_keys=False))
        validate_specification(path, filename + ".schema.json")
    (workspace / "specs/lighting.yaml").write_text(
        yaml.safe_dump(
            {
                "description": "Example formal area light. Source scene.py implements the Blender light; native USD export maps it.",
                "blender_preview": {
                    "formal_key": {
                        "type": "AREA",
                        "power_w": 500,
                        "size_m": 3,
                        "position_m": [0, 0, 3],
                    }
                },
                "target_renderer": "Isaac Sim RTX; appearance pending user review",
            }
        )
    )
    load_extension(workspace / "specs/physics.yaml")
    return workspace


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--kind", choices=("soft_block", "hanging_cloth"), required=True)
    parser.add_argument(
        "--profile", choices=("isaacsim_6_0", "isaacsim_6_1"), default="isaacsim_6_0"
    )
    args = parser.parse_args()
    print(create(args.name, args.kind, args.profile))
