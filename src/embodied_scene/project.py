from __future__ import annotations

import shutil
from pathlib import Path

from .config import repository_root

WORKSPACE_DIRECTORIES = (
    "input/references",
    "specs/rooms",
    "specs/assets",
    "source/structure",
    "source/rooms",
    "source/assets",
    "generated_assets/meshes",
    "generated_assets/textures",
    "generated_assets/backgrounds",
    "build",
    "review",
    "exports",
    "logs",
)


def create_workspace(scene_id: str, root: Path | None = None, force: bool = False) -> Path:
    if not scene_id or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_" for character in scene_id):
        raise ValueError("scene_id must contain lowercase letters, digits, or underscores")

    repository = root or repository_root()
    workspace = repository / "workspaces" / scene_id
    if workspace.exists() and not force:
        raise FileExistsError(f"Workspace already exists: {workspace}")

    for relative in WORKSPACE_DIRECTORIES:
        (workspace / relative).mkdir(parents=True, exist_ok=True)

    templates = repository / "templates"
    shutil.copy2(templates / "task.yaml", workspace / "specs" / "task.yaml")
    shutil.copy2(templates / "scene.yaml", workspace / "specs" / "scene.yaml")
    shutil.copy2(templates / "build_scene.py", workspace / "source" / "build_scene.py")
    (workspace / "input" / "prompt.md").write_text(
        "# Original request\n\nReplace this text with the user's unmodified request.\n",
        encoding="utf-8",
    )
    return workspace
