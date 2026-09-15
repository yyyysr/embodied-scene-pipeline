"""Isolated Microsoft TRELLIS single-request or shared-session worker.

The worker accepts an already reviewed transparent or clean white-background
reference. It never invokes TRELLIS' learned background-removal preprocessing.
"""

from __future__ import annotations

import argparse
import contextlib
import gc
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

ATTENTION_BACKENDS = {"flash-attn", "xformers"}
EVENT_PREFIX = "__EMBODIED_SCENE_EVENT__"


def _read_request() -> dict:
    try:
        request = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON request: {error}") from error
    if not isinstance(request, dict):
        raise TypeError("TRELLIS request must be a JSON object")
    return request


def _required_text(request: dict, key: str) -> str:
    value = request.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()


def _positive_int(request: dict, key: str) -> int:
    value = request.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{key} must be a positive integer")
    return value


def _positive_number(request: dict, key: str) -> float:
    value = request.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{key} must be a positive number")
    return float(value)


def _prepare_image(input_path: Path):
    """Prepare transparent/white-background input without learned segmentation."""
    import cv2
    import numpy as np
    from PIL import Image

    with Image.open(input_path) as source:
        rgba = np.asarray(source.convert("RGBA"), dtype=np.uint8)
    rgb = rgba[..., :3].astype(np.float32)
    source_alpha = rgba[..., 3].astype(np.float32) / 255.0

    if np.any(source_alpha < 0.98):
        alpha = source_alpha
    else:
        height, width = source_alpha.shape
        border_width = max(1, min(height, width) // 32)
        border = np.concatenate(
            (
                rgb[:border_width].reshape(-1, 3),
                rgb[-border_width:].reshape(-1, 3),
                rgb[:, :border_width].reshape(-1, 3),
                rgb[:, -border_width:].reshape(-1, 3),
            )
        )
        if float(np.quantile(border, 0.05)) < 235 or float(border.std()) > 15:
            raise ValueError(
                "Opaque TRELLIS input must have a stable white border; regenerate the "
                "reference with a clean white background or provide meaningful alpha"
            )
        background_color = np.median(border, axis=0)
        color_distance = np.max(np.abs(rgb - background_color), axis=2)
        background_candidate = (color_distance <= 25).astype(np.uint8)
        _, labels = cv2.connectedComponents(background_candidate, connectivity=8)
        border_labels = np.unique(
            np.concatenate((labels[0], labels[-1], labels[:, 0], labels[:, -1]))
        )
        connected_background = np.isin(labels, border_labels) & (background_candidate > 0)
        alpha = np.where(connected_background, 0.0, 1.0).astype(np.float32)

    foreground = np.argwhere(alpha > 0.2)
    if foreground.size == 0:
        raise ValueError("TRELLIS reference contains no detectable foreground")
    coverage = foreground.shape[0] / alpha.size
    if coverage > 0.9:
        raise ValueError("TRELLIS reference foreground covers almost the entire frame")

    y_min, x_min = foreground.min(axis=0)
    y_max, x_max = foreground.max(axis=0)
    object_size = max(int(x_max - x_min + 1), int(y_max - y_min + 1))
    square_size = max(1, round(object_size * 1.2))
    center_x = (int(x_min) + int(x_max)) / 2
    center_y = (int(y_min) + int(y_max)) / 2
    left = round(center_x - square_size / 2)
    top = round(center_y - square_size / 2)
    right = left + square_size
    bottom = top + square_size

    premultiplied = np.clip(rgb * alpha[..., None], 0, 255).astype(np.uint8)
    canvas = np.zeros((square_size, square_size, 3), dtype=np.uint8)
    src_left = max(0, left)
    src_top = max(0, top)
    src_right = min(premultiplied.shape[1], right)
    src_bottom = min(premultiplied.shape[0], bottom)
    if src_left >= src_right or src_top >= src_bottom:
        raise ValueError("TRELLIS reference crop does not intersect the source image")
    dst_left = src_left - left
    dst_top = src_top - top
    canvas[
        dst_top : dst_top + (src_bottom - src_top),
        dst_left : dst_left + (src_right - src_left),
    ] = premultiplied[src_top:src_bottom, src_left:src_right]
    return Image.fromarray(canvas).resize((518, 518), Image.Resampling.LANCZOS)


def _validate_glb(path: Path) -> None:
    if not path.is_file() or path.stat().st_size <= 12:
        raise RuntimeError("TRELLIS produced a missing or empty GLB")
    with path.open("rb") as handle:
        if handle.read(4) != b"glTF":
            raise RuntimeError("TRELLIS output is not a binary GLB")


def _load_pipeline(config: dict):
    model_id = _required_text(config, "model_id")
    attention_backend = config.get("attention_backend", "flash-attn")
    if attention_backend not in ATTENTION_BACKENDS:
        raise ValueError(f"attention_backend must be one of {sorted(ATTENTION_BACKENDS)}")

    os.environ["ATTN_BACKEND"] = attention_backend
    os.environ["SPCONV_ALGO"] = config.get("spconv_algo", "native")
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    import torch
    from trellis.pipelines import TrellisImageTo3DPipeline
    from trellis.utils import postprocessing_utils

    if not torch.cuda.is_available():
        raise RuntimeError("TRELLIS requires CUDA but torch.cuda.is_available() is false")

    pipeline = TrellisImageTo3DPipeline.from_pretrained(model_id)
    pipeline.cuda()
    return pipeline, postprocessing_utils


def _generate_one(runtime, request: dict) -> Path:
    pipeline, postprocessing_utils = runtime
    input_path = Path(_required_text(request, "input_path")).resolve()
    output_path = Path(_required_text(request, "output_path")).resolve()
    if not input_path.is_file() or input_path.stat().st_size == 0:
        raise FileNotFoundError(f"TRELLIS input image does not exist or is empty: {input_path}")
    if output_path.suffix.lower() != ".glb":
        raise ValueError("output_path must end with .glb")

    seed = request.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    simplify = request.get("simplify")
    if not isinstance(simplify, (int, float)) or not 0 <= simplify < 1:
        raise ValueError("simplify must be between 0 inclusive and 1 exclusive")
    texture_size = _positive_int(request, "texture_size")
    image = _prepare_image(input_path)
    outputs = pipeline.run(
        image,
        seed=seed,
        formats=["mesh", "gaussian"],
        preprocess_image=False,
        sparse_structure_sampler_params={
            "steps": _positive_int(request, "sparse_structure_steps"),
            "cfg_strength": _positive_number(request, "sparse_structure_guidance"),
        },
        slat_sampler_params={
            "steps": _positive_int(request, "slat_steps"),
            "cfg_strength": _positive_number(request, "slat_guidance"),
        },
    )
    glb = postprocessing_utils.to_glb(
        outputs["gaussian"][0],
        outputs["mesh"][0],
        simplify=float(simplify),
        texture_size=texture_size,
        verbose=False,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="trellis-", dir=output_path.parent) as temporary:
        temporary_path = Path(temporary) / output_path.name
        glb.export(str(temporary_path))
        _validate_glb(temporary_path)
        os.replace(temporary_path, output_path)
    return output_path


def _generate(request: dict) -> Path:
    runtime = _load_pipeline(request)
    try:
        return _generate_one(runtime, request)
    finally:
        _release_pipeline(runtime)


def _release_pipeline(runtime) -> None:
    del runtime
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def _emit(event: dict) -> None:
    print(f"{EVENT_PREFIX}{json.dumps(event)}", flush=True)


def _serve() -> None:
    runtime = None
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                raise TypeError("Worker message must be a JSON object")
            command = message.get("command")
            if command == "load":
                if runtime is not None:
                    raise RuntimeError("TRELLIS pipeline is already loaded")
                config = message.get("config")
                if not isinstance(config, dict):
                    raise TypeError("load.config must be a JSON object")
                with contextlib.redirect_stdout(sys.stderr):
                    runtime = _load_pipeline(config)
                _emit({"event": "ready"})
            elif command == "generate":
                if runtime is None:
                    raise RuntimeError("TRELLIS pipeline has not been loaded")
                job_id = message.get("job_id")
                request = message.get("request")
                if not isinstance(job_id, str) or not job_id:
                    raise ValueError("generate.job_id must be a non-empty string")
                if not isinstance(request, dict):
                    raise TypeError("generate.request must be a JSON object")
                try:
                    with contextlib.redirect_stdout(sys.stderr):
                        output = _generate_one(runtime, request)
                except Exception as error:  # noqa: BLE001 - isolate one model job
                    _emit({"event": "failed", "job_id": job_id, "error": str(error)})
                else:
                    _emit(
                        {
                            "event": "completed",
                            "job_id": job_id,
                            "output_path": str(output),
                        }
                    )
            elif command == "close":
                if runtime is not None:
                    _release_pipeline(runtime)
                    runtime = None
                _emit({"event": "closed"})
                return
            else:
                raise ValueError(f"Unsupported worker command: {command!r}")
        except Exception as error:
            _emit({"event": "failed", "error": str(error)})
            if runtime is None:
                raise
    if runtime is not None:
        _release_pipeline(runtime)


def _check(attention_backend: str) -> dict:
    os.environ["ATTN_BACKEND"] = attention_backend
    os.environ.setdefault("SPCONV_ALGO", "native")
    import torch
    from trellis.pipelines import TrellisImageTo3DPipeline  # noqa: F401
    from trellis.utils import postprocessing_utils  # noqa: F401

    module_name = "flash_attn" if attention_backend == "flash-attn" else "xformers"
    return {
        "status": "ok",
        "python": sys.executable,
        "torch": torch.__version__,
        "trellis_available": importlib.util.find_spec("trellis") is not None,
        "attention_backend": attention_backend,
        "attention_backend_available": importlib.util.find_spec(module_name) is not None,
        "spconv_available": importlib.util.find_spec("spconv") is not None,
        "cuda_available": torch.cuda.is_available(),
        "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }


def _direct_request(args: argparse.Namespace) -> dict:
    if args.output is None:
        raise ValueError("--output is required with --image")
    return {
        "input_path": str(args.image),
        "output_path": str(args.output),
        "model_id": args.model_id,
        "seed": args.seed,
        "attention_backend": args.attention_backend,
        "spconv_algo": args.spconv_algo,
        "sparse_structure_steps": args.sparse_structure_steps,
        "sparse_structure_guidance": args.sparse_structure_guidance,
        "slat_steps": args.slat_steps,
        "slat_guidance": args.slat_guidance,
        "simplify": args.simplify,
        "texture_size": args.texture_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run isolated TRELLIS image-to-3D")
    parser.add_argument("--check", action="store_true", help="Check imports without weights")
    parser.add_argument("--serve", action="store_true", help="Serve JSONL generation jobs")
    parser.add_argument("--image", type=Path, help="Generate directly from a reference image")
    parser.add_argument("--output", type=Path, help="GLB path for direct generation")
    parser.add_argument("--model-id", default="microsoft/TRELLIS-image-large")
    parser.add_argument(
        "--attention-backend", choices=sorted(ATTENTION_BACKENDS), default="flash-attn"
    )
    parser.add_argument("--spconv-algo", choices=["native", "auto"], default="native")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sparse-structure-steps", type=int, default=12)
    parser.add_argument("--sparse-structure-guidance", type=float, default=7.5)
    parser.add_argument("--slat-steps", type=int, default=12)
    parser.add_argument("--slat-guidance", type=float, default=3.0)
    parser.add_argument("--simplify", type=float, default=0.95)
    parser.add_argument("--texture-size", type=int, default=1024)
    args = parser.parse_args()
    try:
        if args.serve:
            if args.check or args.image:
                raise ValueError("--serve cannot be combined with --check or --image")
            _serve()
            return
        if args.check:
            if args.image:
                raise ValueError("--check and --image cannot be used together")
            with contextlib.redirect_stdout(sys.stderr):
                result = _check(args.attention_backend)
        else:
            request = _direct_request(args) if args.image else _read_request()
            with contextlib.redirect_stdout(sys.stderr):
                result = {"status": "ok", "output_path": str(_generate(request))}
    except Exception as error:
        print(json.dumps({"status": "error", "error": str(error)}), file=sys.stderr)
        raise SystemExit(1) from error
    print(json.dumps(result))


if __name__ == "__main__":
    main()
