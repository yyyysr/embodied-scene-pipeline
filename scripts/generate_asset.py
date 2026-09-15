from __future__ import annotations

import argparse
import json
from pathlib import Path

from embodied_scene.config import load_defaults, repository_root
from embodied_scene.integrations import (
    AssetGenerationRequest,
    FalImageEditor,
    FalImageGenerator,
    Hunyuan3DProvider,
    ImageEditRequest,
    ImageGenerationRequest,
    LocalSD35ImageGenerator,
    LocalTrellisProvider,
    latest_asset_reference,
    select_asset_iteration,
)
from embodied_scene.integrations.environment import load_env_file

MODES = (
    "text-to-3d",
    "text-to-reference-to-3d",
    "source-image-to-reference-to-3d",
)


def _workspace_path(workspace: Path, value: Path, label: str) -> Path:
    resolved = value.resolve() if value.is_absolute() else (workspace / value).resolve()
    try:
        resolved.relative_to(workspace)
    except ValueError as error:
        raise ValueError(f"{label} must stay inside the workspace: {value}") from error
    return resolved


def _reference_prompt(prompt: str, *, source_conditioned: bool) -> str:
    action = (
        f"Reconstruct only this target object from the input image: {prompt}."
        if source_conditioned
        else f"Create a product-style 3D reference image of this object: {prompt}."
    )
    return (
        f"{action} Show exactly one complete physical object, centered on a plain white "
        "background. Use neutral studio lighting and a three-quarter view that clearly "
        "shows its shape. No people, hands, robots, other objects, scenery, text, "
        "watermark, crop truncation, or ground shadow."
    )


def _print_result(workspace: Path, *, status: str, **paths: Path | None) -> None:
    result = {"status": status}
    result.update({key: str(value.relative_to(workspace)) for key, value in paths.items() if value})
    print(json.dumps(result, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate one candidate 3D asset")
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--dimensions", type=float, nargs=3, required=True, metavar=("X", "Y", "Z"))
    parser.add_argument("--source-image", type=Path)
    parser.add_argument("--image-provider", choices=["nano-banana", "gpt-image-2", "sd35"])
    parser.add_argument("--3d-provider", dest="asset_provider", choices=["hunyuan", "trellis"])
    parser.add_argument("--face-count", type=int)
    parser.add_argument("--generate-type", choices=["Normal", "LowPoly", "Geometry"])
    parser.add_argument("--polygon-type", choices=["triangle", "quadrilateral"])
    parser.add_argument("--enable-pbr", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--reference-only", action="store_true")
    parser.add_argument("--regenerate", action="store_true")
    parser.add_argument("--regenerate-reference", action="store_true")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        raise SystemExit(f"Workspace does not exist: {workspace}")
    if args.regenerate_reference and args.mode == "text-to-3d":
        raise ValueError("--regenerate-reference is not valid for text-to-3d")
    if args.reference_only and args.mode == "text-to-3d":
        raise ValueError("--reference-only is not valid for text-to-3d")

    load_env_file(repository_root() / ".env")
    all_defaults = load_defaults()
    defaults = all_defaults["asset_generation"]
    hunyuan_defaults = defaults["hunyuan"]
    provider_3d = args.asset_provider or defaults["provider"]
    if provider_3d == "trellis" and args.mode == "text-to-3d":
        raise ValueError("trellis supports image-conditioned generation only")
    mesh_root = workspace / "generated_assets" / "meshes"
    regenerate = args.regenerate or args.regenerate_reference
    output = select_asset_iteration(mesh_root, args.asset_id, regenerate=regenerate)
    asset_path = output / "asset.glb"
    state_path = output / ".asset.request.json"

    if (
        not regenerate
        and not state_path.exists()
        and asset_path.is_file()
        and asset_path.stat().st_size
    ):
        _print_result(workspace, status="reused", asset=asset_path)
        return

    reference = None
    if args.mode != "text-to-3d":
        reference = (
            None if args.regenerate_reference else latest_asset_reference(mesh_root, args.asset_id)
        )
        if reference is None:
            reference_defaults = defaults["reference_image"]
            configured_provider = reference_defaults.get("provider", "fal")
            image_provider = args.image_provider or (
                reference_defaults["fal_provider"]
                if configured_provider == "fal"
                else configured_provider
            )
            reference_path = output / "reference.png"
            reference_state = output / ".reference.request.json"
            if args.regenerate_reference and not reference_state.exists():
                reference_path.unlink(missing_ok=True)
            prompt = _reference_prompt(
                args.prompt,
                source_conditioned=args.mode == "source-image-to-reference-to-3d",
            )
            if args.mode == "source-image-to-reference-to-3d":
                if image_provider == "sd35":
                    raise ValueError(
                        "sd35 supports text-generated references only; choose a FAL editor "
                        "for source-image-to-reference-to-3d"
                    )
                if args.source_image is None:
                    raise ValueError(
                        "--source-image is required when no reusable reference.png exists"
                    )
                source = _workspace_path(workspace, args.source_image, "source image")
                reference = (
                    FalImageEditor(provider=image_provider)
                    .edit(
                        ImageEditRequest(
                            source,
                            prompt,
                            output,
                            output_filename="reference.png",
                            state_filename=".reference.request.json",
                        )
                    )
                    .image_path
                )
            else:
                if image_provider == "sd35":
                    sd35 = defaults["local_sd35"]
                    generator = LocalSD35ImageGenerator(
                        python_executable=sd35.get("python"),
                        model_id=sd35["model_id"],
                        device=sd35["device"],
                        dtype=sd35["dtype"],
                        width=sd35["width"],
                        height=sd35["height"],
                        num_inference_steps=sd35["num_inference_steps"],
                        guidance_scale=sd35["guidance_scale"],
                        seed=sd35["seed"],
                        negative_prompt=sd35.get("negative_prompt"),
                        enable_model_cpu_offload=sd35["enable_model_cpu_offload"],
                        enable_xformers=sd35["enable_xformers"],
                        enable_attention_slicing=sd35["enable_attention_slicing"],
                        local_files_only=sd35["local_files_only"],
                        timeout_seconds=sd35["timeout_seconds"],
                    )
                else:
                    generator = FalImageGenerator(provider=image_provider)
                reference = generator.generate(ImageGenerationRequest(prompt, output)).image_path

        if args.reference_only:
            _print_result(workspace, status="reference_ready", reference=reference)
            return

    request = AssetGenerationRequest(
        asset_id=args.asset_id,
        prompt=args.prompt,
        target_dimensions=tuple(args.dimensions),
        reference_images=(reference,) if reference else (),
        output_directory=output,
        mode="text-to-3d" if args.mode == "text-to-3d" else "image-to-3d",
        face_count=args.face_count or hunyuan_defaults["face_count"],
        enable_pbr=(hunyuan_defaults["enable_pbr"] if args.enable_pbr is None else args.enable_pbr),
        generate_type=args.generate_type or hunyuan_defaults["generate_type"],
        polygon_type=args.polygon_type or hunyuan_defaults["polygon_type"],
    )
    if provider_3d == "trellis":
        trellis = defaults["local_trellis"]
        provider = LocalTrellisProvider(
            python_executable=trellis.get("python"),
            repo_dir=repository_root() / trellis.get("repo_dir", "third_party/TRELLIS"),
            model_id=trellis["model_id"],
            attention_backend=trellis["attention_backend"],
            spconv_algo=trellis["spconv_algo"],
            seed=trellis["seed"],
            sparse_structure_steps=trellis["sparse_structure_steps"],
            sparse_structure_guidance=trellis["sparse_structure_guidance"],
            slat_steps=trellis["slat_steps"],
            slat_guidance=trellis["slat_guidance"],
            simplify=trellis["simplify"],
            texture_size=trellis["texture_size"],
            timeout_seconds=trellis["timeout_seconds"],
        )
    else:
        provider = Hunyuan3DProvider(
            poll_interval_seconds=hunyuan_defaults["poll_interval_seconds"],
            timeout_seconds=hunyuan_defaults["timeout_seconds"],
            text_endpoint=hunyuan_defaults["text_endpoint"],
            image_endpoint=hunyuan_defaults["image_endpoint"],
        )
    result = provider.generate(request)
    _print_result(
        workspace,
        status="generated_unreviewed",
        asset=result.asset_path,
        reference=reference,
    )


if __name__ == "__main__":
    main()
