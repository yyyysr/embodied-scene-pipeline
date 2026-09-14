from __future__ import annotations

from pathlib import Path


def _workspace_file(workspace: Path, configured: str, label: str) -> dict | None:
    candidate = (workspace / configured).resolve()
    try:
        candidate.relative_to(workspace.resolve())
    except ValueError:
        return {
            "severity": "major",
            "entity_id": "scene_background",
            "message": f"{label} escapes the workspace: {configured}",
            "suggested_fix": "Use a workspace-relative generated background path.",
        }
    if not candidate.is_file() or candidate.stat().st_size == 0:
        return {
            "severity": "major",
            "entity_id": "scene_background",
            "message": f"{label} is missing or empty: {configured}",
            "suggested_fix": "Regenerate the optional background or select a Blender fallback.",
        }
    return None


def validate_background(scene_spec: dict, workspace: Path) -> tuple[dict[str, bool], list[dict]]:
    world = scene_spec.get("world") or {}
    if world.get("background_mode") != "3dgs":
        return {
            "background_input_exists": True,
            "background_asset_exists": True,
            "environment_image_exists": True,
        }, []

    findings = []
    checks = {}
    for field, label in (
        ("background_input", "3DGS input image"),
        ("background_asset", "3DGS full-resolution SPZ"),
        ("environment_image", "3DGS panorama"),
    ):
        configured = world.get(field)
        if field == "environment_image" and not configured:
            checks["environment_image_exists"] = True
            continue
        finding = (
            _workspace_file(workspace, configured, label)
            if configured
            else {
                "severity": "major",
                "entity_id": "scene_background",
                "message": f"{label} is not configured.",
                "suggested_fix": "Generate the optional background or select a Blender fallback.",
            }
        )
        checks[f"{field}_exists"] = finding is None
        if finding:
            findings.append(finding)
    return checks, findings
