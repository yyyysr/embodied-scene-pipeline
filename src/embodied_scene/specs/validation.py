from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from embodied_scene.config import load_yaml, repository_root


class _LocalResolver(jsonschema.RefResolver):
    pass


def validate_specification(data_path: Path, schema_name: str, root: Path | None = None) -> dict:
    repository = root or repository_root()
    schema_path = repository / "schemas" / schema_name
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    store = {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in (repository / "schemas").glob("*.schema.json")
    }
    resolver = _LocalResolver.from_schema(schema, store=store)
    data = load_yaml(data_path)
    jsonschema.Draft202012Validator(schema, resolver=resolver).validate(data)
    return data

