from __future__ import annotations

import json
from pathlib import Path


def new_report(scene_id: str) -> dict:
    return {"scene_id": scene_id, "status": "pass", "checks": {}, "findings": []}


def write_report(report: dict, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")

