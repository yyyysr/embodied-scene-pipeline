from pathlib import Path

from embodied_scene.project import create_workspace


def test_create_workspace(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "templates").mkdir(parents=True)
    (root / "templates" / "task.yaml").write_text("id: replace_me\n", encoding="utf-8")
    (root / "templates" / "scene.yaml").write_text("id: replace_me\n", encoding="utf-8")
    (root / "templates" / "build_scene.py").write_text(
        "def build_scene(context, scene_spec):\n    pass\n",
        encoding="utf-8",
    )
    (root / "templates" / "physics.yaml").write_text("version: 1\n", encoding="utf-8")
    workspace = create_workspace("demo_01", root=root)
    assert (workspace / "input" / "prompt.md").exists()
    assert (workspace / "specs" / "task.yaml").exists()
    assert (workspace / "source" / "build_scene.py").exists()
    assert (workspace / "review").is_dir()
    assert (workspace / "specs" / "physics.yaml").exists()

    assert not (workspace / "generated_assets").exists()
    assert not (workspace / "logs").exists()
