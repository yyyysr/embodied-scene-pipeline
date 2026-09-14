from __future__ import annotations

from pathlib import Path

import yaml


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise TypeError(f"Expected a mapping in {path}")
    return data


def load_defaults(root: Path | None = None) -> dict:
    root = root or repository_root()
    return load_yaml(root / "config" / "defaults.yaml")
