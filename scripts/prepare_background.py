from __future__ import annotations

import argparse
import json
from pathlib import Path

from embodied_scene.backgrounds import next_background_iteration
from embodied_scene.config import load_defaults, repository_root
from embodied_scene.integrations import (
    CleanPlateRequest,
    FalImageEditor,
    StaticBackgroundRequest,
    WorldLabsProvider,
)
from embodied_scene.integrations.environment import load_env_file


def _inside_workspace(workspace: Path, value: Path, label: str) -> Path:
    resolved = value.resolve() if value.is_absolute() else (workspace / value).resolve()
    try:
        resolved.relative_to(workspace)
    except ValueError as error:
        raise ValueError(f"{label} must stay inside the workspace: {value}") from error
    return resolved


def _output_directory(
    workspace: Path, configured: Path | None, preferred: Path | None = None
) -> Path:
    root = workspace / "generated_assets" / "backgrounds"
    if configured is None:
        if preferred is not None and preferred.parent == root:
            return preferred
        return next_background_iteration(root)
    output = _inside_workspace(workspace, configured, "output directory")
    try:
        output.relative_to(root)
    except ValueError as error:
        raise ValueError("Output directory must be under generated_assets/backgrounds") from error
    output.mkdir(parents=True, exist_ok=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare an optional static 3DGS background")
    parser.add_argument("workspace", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)

    clean = subparsers.add_parser("clean-plate", help="Remove task entities through FAL")
    clean.add_argument("--image", type=Path, required=True)
    clean.add_argument("--prompt", required=True)
    clean.add_argument("--provider", choices=["nano-banana", "gpt-image-2"])
    clean.add_argument("--mask", type=Path)
    clean.add_argument("--output", type=Path)

    world = subparsers.add_parser("world", help="Generate a World Labs 3DGS background")
    world.add_argument("--image", type=Path, required=True)
    world.add_argument("--prompt", required=True)
    world.add_argument("--output", type=Path)

    args = parser.parse_args()
    load_env_file(repository_root() / ".env")
    defaults = load_defaults()["background_generation"]
    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        raise SystemExit(f"Workspace does not exist: {workspace}")
    image = _inside_workspace(workspace, args.image, "input image")
    preferred = image.parent if image.parent.name.startswith("iteration_") else None
    output = _output_directory(
        workspace, args.output, preferred if args.command == "world" else None
    )

    if args.command == "clean-plate":
        mask = _inside_workspace(workspace, args.mask, "mask image") if args.mask else None
        provider = args.provider or defaults["clean_plate"]["fal_provider"]
        result = FalImageEditor(provider=provider).create_clean_plate(
            CleanPlateRequest(image, args.prompt, output, mask)
        )
        summary = {
            "status": "completed",
            "provider": result.provider,
            "model": result.model,
            "clean_plate": str(result.image_path.relative_to(workspace)),
        }
    else:
        world_defaults = defaults["world"]
        result = WorldLabsProvider(
            poll_interval_seconds=world_defaults["poll_interval_seconds"],
            timeout_seconds=world_defaults["timeout_seconds"],
        ).generate(StaticBackgroundRequest(workspace.name, args.prompt, image, output))
        summary = {
            "status": "completed",
            "background_asset": str(result.full_resolution_splat.relative_to(workspace)),
            "splats": {
                key: str(path.relative_to(workspace)) for key, path in result.splats.items()
            },
            **(
                {"collider_mesh": str(result.collider_mesh.relative_to(workspace))}
                if result.collider_mesh
                else {}
            ),
            **(
                {"environment_image": str(result.panorama.relative_to(workspace))}
                if result.panorama
                else {}
            ),
            **(
                {"thumbnail": str(result.thumbnail.relative_to(workspace))}
                if result.thumbnail
                else {}
            ),
        }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
