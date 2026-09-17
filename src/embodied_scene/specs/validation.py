from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from referencing import Registry, Resource

from embodied_scene.config import load_yaml, repository_root


def validate_specification(data_path: Path, schema_name: str, root: Path | None = None) -> dict:
    repository = root or repository_root()
    schema_path = repository / "schemas" / schema_name
    # Absolute resource IDs keep sibling refs and local fragments in their own
    # schema scope, including after returning from assembly.schema.json.
    resources = {}
    for path in (repository / "schemas").glob("*.schema.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        uri = path.resolve().as_uri()
        document["$id"] = uri
        resources[uri] = Resource.from_contents(document)
    registry = Registry().with_resources(resources.items())
    schema = resources[schema_path.resolve().as_uri()].contents
    data = load_yaml(data_path)
    jsonschema.Draft202012Validator(schema, registry=registry).validate(data)
    return data
