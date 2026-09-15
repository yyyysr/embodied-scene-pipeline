from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import TextIO

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from embodied_scene.config import load_defaults, repository_root
from embodied_scene.integrations import (
    AssetGenerationRequest,
    ImageGenerationRequest,
    LocalSD35ImageGenerator,
    LocalTrellisProvider,
)
from embodied_scene.integrations.image_editing import validate_image_input

PROVIDERS = ("sd35", "trellis")


def _required_text(job: dict, key: str, line_number: int) -> str:
    value = job.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Line {line_number}: {key} must be a non-empty string")
    return value.strip()


def _read_jobs(stream: TextIO) -> list[tuple[int, dict]]:
    jobs = []
    identifiers = set()
    for line_number, line in enumerate(stream, start=1):
        if not line.strip():
            continue
        try:
            job = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Line {line_number}: invalid JSON: {error.msg}") from error
        if not isinstance(job, dict):
            raise TypeError(f"Line {line_number}: each JSONL job must be an object")
        job_id = _required_text(job, "job_id", line_number)
        if not re.fullmatch(r"[a-z0-9_]+", job_id):
            raise ValueError(
                f"Line {line_number}: job_id must contain lowercase letters, "
                "digits, or underscores"
            )
        if job_id in identifiers:
            raise ValueError(f"Line {line_number}: duplicate job_id: {job_id}")
        identifiers.add(job_id)
        jobs.append((line_number, job))
    if not jobs:
        raise ValueError("JSONL input contains no jobs")
    return jobs


def _output_path(job: dict, line_number: int, suffix: str) -> Path:
    output_path = Path(_required_text(job, "output_path", line_number)).resolve()
    if output_path.suffix.lower() != suffix:
        raise ValueError(f"Line {line_number}: output_path must end with {suffix}")
    return output_path


def _sd35_request(job: dict, line_number: int) -> ImageGenerationRequest:
    prompt = _required_text(job, "prompt", line_number)
    output_path = _output_path(job, line_number, ".png")
    return ImageGenerationRequest(prompt, output_path.parent, output_path.name)


def _trellis_request(job: dict, line_number: int) -> AssetGenerationRequest:
    job_id = _required_text(job, "job_id", line_number)
    prompt = _required_text(job, "prompt", line_number)
    input_path = validate_image_input(
        Path(_required_text(job, "input_path", line_number))
    )
    output_path = _output_path(job, line_number, ".glb")
    if output_path.name != "asset.glb":
        raise ValueError(
            f"Line {line_number}: TRELLIS output_path must use the canonical "
            "filename asset.glb"
        )
    dimensions = job.get("target_dimensions")
    if (
        not isinstance(dimensions, list)
        or len(dimensions) != 3
        or any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value <= 0
            for value in dimensions
        )
    ):
        raise ValueError(
            f"Line {line_number}: target_dimensions must contain three positive numbers"
        )
    return AssetGenerationRequest(
        asset_id=job_id,
        prompt=prompt,
        target_dimensions=tuple(float(value) for value in dimensions),
        reference_images=(input_path,),
        output_directory=output_path.parent,
        mode="image-to-3d",
    )


def _sd35_provider(defaults: dict) -> LocalSD35ImageGenerator:
    config = defaults["local_sd35"]
    return LocalSD35ImageGenerator(
        python_executable=config.get("python"),
        model_id=config["model_id"],
        device=config["device"],
        dtype=config["dtype"],
        width=config["width"],
        height=config["height"],
        num_inference_steps=config["num_inference_steps"],
        guidance_scale=config["guidance_scale"],
        seed=config["seed"],
        negative_prompt=config.get("negative_prompt"),
        enable_model_cpu_offload=config["enable_model_cpu_offload"],
        enable_xformers=config["enable_xformers"],
        enable_attention_slicing=config["enable_attention_slicing"],
        local_files_only=config["local_files_only"],
        timeout_seconds=config["timeout_seconds"],
    )


def _trellis_provider(defaults: dict) -> LocalTrellisProvider:
    config = defaults["local_trellis"]
    repo_dir = Path(config.get("repo_dir", "third_party/TRELLIS"))
    if not repo_dir.is_absolute():
        repo_dir = repository_root() / repo_dir
    return LocalTrellisProvider(
        python_executable=config.get("python"),
        repo_dir=repo_dir,
        model_id=config["model_id"],
        attention_backend=config["attention_backend"],
        spconv_algo=config["spconv_algo"],
        seed=config["seed"],
        sparse_structure_steps=config["sparse_structure_steps"],
        sparse_structure_guidance=config["sparse_structure_guidance"],
        slat_steps=config["slat_steps"],
        slat_guidance=config["slat_guidance"],
        simplify=config["simplify"],
        texture_size=config["texture_size"],
        timeout_seconds=config["timeout_seconds"],
    )


def _emit(stream: TextIO, event: dict) -> None:
    stream.write(json.dumps(event) + "\n")
    stream.flush()


def _run_sd35(jobs: list[tuple[int, dict]], defaults: dict, output: TextIO) -> None:
    prepared = [
        (job["job_id"], _sd35_request(job, line_number))
        for line_number, job in jobs
    ]
    provider = _sd35_provider(defaults)
    with provider.session() as session:
        for job_id, request in prepared:
            result = session.generate(request)
            _emit(
                output,
                {
                    "status": "completed",
                    "provider": "sd35",
                    "job_id": job_id,
                    "output_path": str(result.image_path),
                },
            )


def _run_trellis(jobs: list[tuple[int, dict]], defaults: dict, output: TextIO) -> None:
    prepared = [
        (job["job_id"], _trellis_request(job, line_number))
        for line_number, job in jobs
    ]
    provider = _trellis_provider(defaults)
    with provider.session() as session:
        for job_id, request in prepared:
            result = session.generate(request)
            _emit(
                output,
                {
                    "status": "completed",
                    "provider": "trellis",
                    "job_id": job_id,
                    "output_path": str(result.asset_path),
                },
            )


def main(
    argv: list[str] | None = None,
    *,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Generate local SD3.5 references or TRELLIS assets from JSONL"
    )
    parser.add_argument("--provider", choices=PROVIDERS, required=True)
    parser.add_argument(
        "--input",
        default="-",
        help="JSONL input path; omit or use - to read stdin",
    )
    args = parser.parse_args(argv)
    output = output_stream or sys.stdout
    try:
        if input_stream is not None:
            jobs = _read_jobs(input_stream)
        elif args.input == "-":
            jobs = _read_jobs(sys.stdin)
        else:
            with Path(args.input).open("r", encoding="utf-8") as handle:
                jobs = _read_jobs(handle)
        defaults = load_defaults()["asset_generation"]
        if args.provider == "sd35":
            _run_sd35(jobs, defaults, output)
        else:
            _run_trellis(jobs, defaults, output)
    except Exception as error:  # noqa: BLE001 - stable command error boundary
        _emit(output, {"status": "error", "error": str(error)})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
