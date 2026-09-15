"""Isolated Stable Diffusion 3.5 single-request or shared-session worker."""

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

DTYPES = {"float16", "bfloat16", "float32"}
DEVICES = {"cuda", "cpu"}
EVENT_PREFIX = "__EMBODIED_SCENE_EVENT__"


def _read_request() -> dict:
    try:
        request = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON request: {error}") from error
    if not isinstance(request, dict):
        raise TypeError("SD3.5 request must be a JSON object")
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


def _load_pipeline(config: dict):
    model_id = _required_text(config, "model_id")
    device = config.get("device", "cuda")
    dtype_name = config.get("dtype", "float16")
    if device not in DEVICES:
        raise ValueError(f"device must be one of {sorted(DEVICES)}")
    if dtype_name not in DTYPES:
        raise ValueError(f"dtype must be one of {sorted(DTYPES)}")
    if device == "cpu" and dtype_name == "float16":
        raise ValueError("float16 is not supported for CPU inference; use float32")

    import torch
    from diffusers import StableDiffusion3Pipeline

    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but torch.cuda.is_available() is false")

    dtype = getattr(torch, dtype_name)
    pipeline = StableDiffusion3Pipeline.from_pretrained(
        model_id,
        torch_dtype=dtype,
        local_files_only=bool(config.get("local_files_only", False)),
    )
    cpu_offload = bool(config.get("enable_model_cpu_offload", True))
    if cpu_offload:
        if device != "cuda":
            raise ValueError("enable_model_cpu_offload requires device=cuda")
        pipeline.enable_model_cpu_offload()
    else:
        pipeline = pipeline.to(device)

    if config.get("enable_xformers", True):
        pipeline.enable_xformers_memory_efficient_attention()
    if config.get("enable_attention_slicing", True):
        pipeline.enable_attention_slicing()
    return pipeline


def _generate_one(pipeline, request: dict) -> Path:
    prompt = _required_text(request, "prompt")
    output_path = Path(_required_text(request, "output_path")).resolve()
    if output_path.suffix.lower() != ".png":
        raise ValueError("output_path must end with .png")

    width = _positive_int(request, "width")
    height = _positive_int(request, "height")
    steps = _positive_int(request, "num_inference_steps")
    guidance_scale = request.get("guidance_scale")
    if not isinstance(guidance_scale, (int, float)) or guidance_scale < 0:
        raise ValueError("guidance_scale must be a non-negative number")
    seed = request.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a non-negative integer")

    import torch

    generator = torch.Generator(device="cpu").manual_seed(seed)
    inference = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_inference_steps": steps,
        "guidance_scale": float(guidance_scale),
        "num_images_per_prompt": 1,
        "generator": generator,
    }
    negative_prompt = request.get("negative_prompt")
    if isinstance(negative_prompt, str) and negative_prompt.strip():
        inference["negative_prompt"] = negative_prompt.strip()

    image = pipeline(**inference).images[0]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sd35-", dir=output_path.parent) as temporary:
        temporary_path = Path(temporary) / output_path.name
        image.save(temporary_path, format="PNG")
        if not temporary_path.is_file() or temporary_path.stat().st_size == 0:
            raise RuntimeError("SD3.5 produced an empty image")
        os.replace(temporary_path, output_path)
    return output_path


def _generate(request: dict) -> Path:
    pipeline = _load_pipeline(request)
    try:
        return _generate_one(pipeline, request)
    finally:
        _release_pipeline(pipeline)


def _release_pipeline(pipeline) -> None:
    del pipeline
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
    pipeline = None
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                raise TypeError("Worker message must be a JSON object")
            command = message.get("command")
            if command == "load":
                if pipeline is not None:
                    raise RuntimeError("SD3.5 pipeline is already loaded")
                config = message.get("config")
                if not isinstance(config, dict):
                    raise TypeError("load.config must be a JSON object")
                with contextlib.redirect_stdout(sys.stderr):
                    pipeline = _load_pipeline(config)
                _emit({"event": "ready"})
            elif command == "generate":
                if pipeline is None:
                    raise RuntimeError("SD3.5 pipeline has not been loaded")
                job_id = message.get("job_id")
                request = message.get("request")
                if not isinstance(job_id, str) or not job_id:
                    raise ValueError("generate.job_id must be a non-empty string")
                if not isinstance(request, dict):
                    raise TypeError("generate.request must be a JSON object")
                try:
                    with contextlib.redirect_stdout(sys.stderr):
                        output = _generate_one(pipeline, request)
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
                if pipeline is not None:
                    _release_pipeline(pipeline)
                    pipeline = None
                _emit({"event": "closed"})
                return
            else:
                raise ValueError(f"Unsupported worker command: {command!r}")
        except Exception as error:
            _emit({"event": "failed", "error": str(error)})
            if pipeline is None:
                raise
    if pipeline is not None:
        _release_pipeline(pipeline)


def _check() -> dict:
    import diffusers
    import torch
    import transformers
    from diffusers import StableDiffusion3Pipeline  # noqa: F401

    return {
        "status": "ok",
        "python": sys.executable,
        "torch": torch.__version__,
        "diffusers": diffusers.__version__,
        "transformers": transformers.__version__,
        "xformers_available": importlib.util.find_spec("xformers") is not None,
        "cuda_available": torch.cuda.is_available(),
        "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }


def _direct_request(args: argparse.Namespace) -> dict:
    if args.output is None:
        raise ValueError("--output is required with --prompt")
    return {
        "prompt": args.prompt,
        "negative_prompt": args.negative_prompt,
        "output_path": str(args.output),
        "model_id": args.model_id,
        "device": args.device,
        "dtype": args.dtype,
        "width": args.width,
        "height": args.height,
        "num_inference_steps": args.steps,
        "guidance_scale": args.guidance_scale,
        "seed": args.seed,
        "enable_model_cpu_offload": args.enable_model_cpu_offload,
        "enable_xformers": args.enable_xformers,
        "enable_attention_slicing": True,
        "local_files_only": args.local_files_only,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run isolated SD3.5 image generation")
    parser.add_argument(
        "--check", action="store_true", help="Check imports without loading weights"
    )
    parser.add_argument("--serve", action="store_true", help="Serve JSONL generation jobs")
    parser.add_argument("--prompt", help="Generate directly without a scene workspace")
    parser.add_argument("--output", type=Path, help="PNG path for direct generation")
    parser.add_argument("--model-id", default="stabilityai/stable-diffusion-3.5-medium")
    parser.add_argument("--device", choices=sorted(DEVICES), default="cuda")
    parser.add_argument("--dtype", choices=sorted(DTYPES), default="float16")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--steps", type=int, default=25)
    parser.add_argument("--guidance-scale", type=float, default=7.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--negative-prompt")
    parser.add_argument(
        "--enable-model-cpu-offload",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--enable-xformers", action="store_true")
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.serve:
            if args.check or args.prompt:
                raise ValueError("--serve cannot be combined with --check or --prompt")
            _serve()
            return
        if args.check:
            if args.prompt:
                raise ValueError("--check and --prompt cannot be used together")
            with contextlib.redirect_stdout(sys.stderr):
                result = _check()
        else:
            request = _direct_request(args) if args.prompt else _read_request()
            with contextlib.redirect_stdout(sys.stderr):
                result = {"status": "ok", "output_path": str(_generate(request))}
    except Exception as error:
        print(json.dumps({"status": "error", "error": str(error)}), file=sys.stderr)
        raise SystemExit(1) from error
    print(json.dumps(result))


if __name__ == "__main__":
    main()
