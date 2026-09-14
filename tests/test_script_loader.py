from pathlib import Path

import pytest

from blender_runtime.script_loader import load_entrypoint, resolve_source_script


def test_load_agent_authored_entrypoint(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    script = source / "build_scene.py"
    script.write_text(
        "def build_scene(context, scene_spec):\n    return scene_spec['id']\n",
        encoding="utf-8",
    )
    entrypoint = load_entrypoint(
        tmp_path,
        {
            "script": "source/build_scene.py",
            "entrypoint": "build_scene",
        },
    )
    assert entrypoint(None, {"id": "demo"}) == "demo"


def test_source_script_cannot_escape_workspace_source(tmp_path: Path) -> None:
    outside = tmp_path / "outside.py"
    outside.write_text("pass\n", encoding="utf-8")
    with pytest.raises(ValueError, match="workspace/source"):
        resolve_source_script(tmp_path, "source/../outside.py")


def test_missing_entrypoint_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "build_scene.py").write_text("VALUE = 1\n", encoding="utf-8")
    with pytest.raises(TypeError, match="entry point"):
        load_entrypoint(
            tmp_path,
            {"script": "source/build_scene.py", "entrypoint": "build_scene"},
        )
