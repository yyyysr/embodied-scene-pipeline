"""Run the local scene assembly editor; uv sync --extra editor first."""

import argparse
import os
import shutil
from pathlib import Path

import uvicorn

from embodied_scene.editor import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--blender", default=os.environ.get("BLENDER_BIN", "blender"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    blender = shutil.which(args.blender)
    if not blender:
        parser.error("Blender not found; pass --blender or set BLENDER_BIN")
    print(f"Scene editor: http://127.0.0.1:{args.port}")
    uvicorn.run(create_app(args.workspace, blender), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
