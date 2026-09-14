from __future__ import annotations

import argparse
from pathlib import Path

from embodied_scene.specs import validate_specification


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate task and scene YAML")
    parser.add_argument("scene", type=Path)
    parser.add_argument("--task", type=Path)
    args = parser.parse_args()
    validate_specification(args.scene, "scene.schema.json")
    if args.task:
        validate_specification(args.task, "task.schema.json")
    print("Specifications are valid")


if __name__ == "__main__":
    main()

