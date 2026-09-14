from __future__ import annotations

import argparse

from embodied_scene.project import create_workspace


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an embodied scene workspace")
    parser.add_argument("scene_id")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    print(create_workspace(args.scene_id, force=args.force))


if __name__ == "__main__":
    main()

