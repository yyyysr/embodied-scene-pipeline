"""Export an existing modeled scene through the same pipeline used by run_blender."""

import argparse
from pathlib import Path

from embodied_scene.usd.delivery import export_scene


def main():
    parser = argparse.ArgumentParser(description="Deliver scene.usdc with physics and textures")
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--blend", type=Path, help="Defaults to workspace/build/scene.blend")
    parser.add_argument("--physics", type=Path, help="Defaults to workspace/specs/physics.yaml")
    parser.add_argument(
        "--debug", action="store_true", help="Retain temporary USD in build/usd_debug"
    )
    args = parser.parse_args()
    result = export_scene(
        args.blend or args.workspace / "build/scene.blend",
        args.physics or args.workspace / "specs/physics.yaml",
        args.workspace,
        debug=args.debug,
    )
    print(f"USD static checks: {result['status']}; Isaac Sim validation: pending_user")
    for error in result.get("errors", []):
        print(error)
    raise SystemExit(0 if result["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
