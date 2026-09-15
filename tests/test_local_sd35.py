import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from embodied_scene.integrations import ImageGenerationRequest, LocalSD35ImageGenerator


def _worker(tmp_path: Path) -> Path:
    worker = tmp_path / "sd35_worker.py"
    worker.write_text("# fake worker", encoding="utf-8")
    return worker


def test_local_sd35_sends_one_worker_request_and_returns_reference(tmp_path: Path) -> None:
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        payload = json.loads(kwargs["input"])
        Path(payload["output_path"]).write_bytes(b"png")
        return SimpleNamespace(returncode=0, stdout='{"status":"ok"}', stderr="")

    generator = LocalSD35ImageGenerator(
        python_executable="asset-python",
        worker_path=_worker(tmp_path),
        seed=17,
        run_command=run,
    )
    result = generator.generate(
        ImageGenerationRequest("One ceramic mug", tmp_path / "iteration_001")
    )

    assert result.image_path == tmp_path / "iteration_001" / "reference.png"
    assert result.provider == "local"
    command, options = calls[0]
    assert command == ["asset-python", str(generator.worker_path)]
    payload = json.loads(options["input"])
    assert payload["prompt"] == "One ceramic mug"
    assert payload["seed"] == 17
    assert payload["num_inference_steps"] == 25
    assert payload["enable_xformers"] is False
    assert options["timeout"] == 900.0


def test_local_sd35_reuses_existing_reference_without_worker(tmp_path: Path) -> None:
    output = tmp_path / "iteration_001"
    output.mkdir()
    reference = output / "reference.png"
    reference.write_bytes(b"existing")

    generator = LocalSD35ImageGenerator(
        worker_path=_worker(tmp_path),
        run_command=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()),
    )
    result = generator.generate(ImageGenerationRequest("One mug", output))
    assert result.image_path == reference


def test_local_sd35_reports_worker_failure(tmp_path: Path) -> None:
    def run(*_args, **_kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="missing diffusers")

    generator = LocalSD35ImageGenerator(worker_path=_worker(tmp_path), run_command=run)
    with pytest.raises(RuntimeError, match="missing diffusers"):
        generator.generate(ImageGenerationRequest("One mug", tmp_path / "out"))


def test_local_sd35_translates_worker_timeout(tmp_path: Path) -> None:
    def run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("sd35", 5)

    generator = LocalSD35ImageGenerator(
        worker_path=_worker(tmp_path), timeout_seconds=5, run_command=run
    )
    with pytest.raises(TimeoutError, match="5 seconds"):
        generator.generate(ImageGenerationRequest("One mug", tmp_path / "out"))
