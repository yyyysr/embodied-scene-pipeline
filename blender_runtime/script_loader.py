from __future__ import annotations

import hashlib
import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path


def resolve_source_script(workspace: Path, configured_path: str) -> Path:
    """Resolve a configured builder without allowing it to escape source/."""
    source_root = (workspace / "source").resolve()
    script_path = (workspace / configured_path).resolve()
    try:
        script_path.relative_to(source_root)
    except ValueError as error:
        raise ValueError("Scene builder must be located under workspace/source") from error
    if not script_path.is_file():
        raise FileNotFoundError(f"Scene builder was not found: {script_path}")
    return script_path


def load_entrypoint(workspace: Path, implementation: dict) -> Callable:
    script_path = resolve_source_script(workspace, implementation["script"])
    source_root = str((workspace / "source").resolve())
    if source_root not in sys.path:
        # Keep this available while the entry point runs so it can lazily import
        # sibling structure, room, and asset modules.
        sys.path.insert(0, source_root)

    digest = hashlib.sha256(str(script_path).encode("utf-8")).hexdigest()[:12]
    module_spec = importlib.util.spec_from_file_location(f"scene_builder_{digest}", script_path)
    if module_spec is None or module_spec.loader is None:
        raise ImportError(f"Cannot load scene builder: {script_path}")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)

    entrypoint_name = implementation["entrypoint"]
    entrypoint = getattr(module, entrypoint_name, None)
    if not callable(entrypoint):
        raise TypeError(f"Scene builder has no callable entry point: {entrypoint_name}")
    return entrypoint
