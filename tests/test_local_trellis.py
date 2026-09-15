import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from embodied_scene.integrations import (
    AssetGenerationRequest,
    LocalTrellisProvider,
)


def _worker(tmp_path: Path) -> Path:
    worker = tmp_path / "trellis_worker.py"
    worker.write_text("# fake worker", encoding="utf-8")
    return worker


def _request(tmp_path: Path, *, mode: str = "image-to-3d") -> AssetGenerationRequest:
    reference = tmp_path / "reference.png"
    reference.write_bytes(b"image")
    return AssetGenerationRequest(
        asset_id="ceramic_mug",
        prompt="One ceramic mug",
        target_dimensions=(0.11, 0.08, 0.1),
        reference_images=(reference,),
        output_directory=tmp_path / "iteration_001",
        mode=mode,
    )


def test_local_trellis_sends_worker_request_and_returns_glb(tmp_path: Path) -> None:
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        payload = json.loads(kwargs["input"])
        Path(payload["output_path"]).write_bytes(b"glTF generated")
        return SimpleNamespace(returncode=0, stdout='{"status":"ok"}', stderr="")

    provider = LocalTrellisProvider(
        python_executable="trellis-python",
        worker_path=_worker(tmp_path),
        seed=7,
        run_command=run,
    )
    result = provider.generate(_request(tmp_path))

    assert result.asset_path == tmp_path / "iteration_001" / "asset.glb"
    assert result.provider == "local"
    command, options = calls[0]
    assert command == ["trellis-python", str(provider.worker_path)]
    payload = json.loads(options["input"])
    assert payload["seed"] == 7
    assert payload["model_id"] == "microsoft/TRELLIS-image-large"
    assert payload["sparse_structure_steps"] == 12
    assert payload["slat_guidance"] == 3.0
    assert options["timeout"] == 1800.0


def test_local_trellis_reuses_existing_asset(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request.output_directory.mkdir()
    asset = request.output_directory / "asset.glb"
    asset.write_bytes(b"glTF existing")
    provider = LocalTrellisProvider(
        worker_path=_worker(tmp_path),
        run_command=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()),
    )
    assert provider.generate(request).asset_path == asset


def test_local_trellis_rejects_text_to_3d(tmp_path: Path) -> None:
    provider = LocalTrellisProvider(worker_path=_worker(tmp_path))
    with pytest.raises(ValueError, match="image-to-3d only"):
        provider.generate(_request(tmp_path, mode="text-to-3d"))


def test_local_trellis_reports_worker_failure(tmp_path: Path) -> None:
    def run(*_args, **_kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="missing trellis")

    provider = LocalTrellisProvider(worker_path=_worker(tmp_path), run_command=run)
    with pytest.raises(RuntimeError, match="missing trellis"):
        provider.generate(_request(tmp_path))


def test_local_trellis_translates_worker_timeout(tmp_path: Path) -> None:
    def run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("trellis", 5)

    provider = LocalTrellisProvider(
        worker_path=_worker(tmp_path), timeout_seconds=5, run_command=run
    )
    with pytest.raises(TimeoutError, match="5 seconds"):
        provider.generate(_request(tmp_path))
