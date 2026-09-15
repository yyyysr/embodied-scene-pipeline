import json
import sys
from io import StringIO
from pathlib import Path

import pytest

from embodied_scene.integrations import (
    AssetGenerationRequest,
    ImageGenerationRequest,
    LocalSD35ImageGenerator,
    LocalTrellisProvider,
)
from local_runtime import sd35_worker, trellis_worker

FAKE_WORKER = """
import json
import os
import sys
from pathlib import Path

EVENT_PREFIX = "__EMBODIED_SCENE_EVENT__"
root = Path(__file__).parent
for line in sys.stdin:
    message = json.loads(line)
    command = message["command"]
    if command == "load":
        marker = root / "loads.txt"
        count = int(marker.read_text() or "0") if marker.exists() else 0
        marker.write_text(str(count + 1))
        (root / "environment.json").write_text(json.dumps({
            "PYTHONPATH": os.environ.get("PYTHONPATH"),
            "NUMBA_CACHE_DIR": os.environ.get("NUMBA_CACHE_DIR"),
            "WARP_CACHE_PATH": os.environ.get("WARP_CACHE_PATH"),
        }))
        print("Loading ..0%", end="", flush=True)
        print(EVENT_PREFIX + json.dumps({"event": "ready"}), flush=True)
    elif command == "generate":
        output = Path(message["request"]["output_path"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"glTF generated" if output.suffix == ".glb" else b"png")
        print("Sampling ..0%", end="", flush=True)
        print(EVENT_PREFIX + json.dumps({
            "event": "completed",
            "job_id": message["job_id"],
            "output_path": str(output),
        }), flush=True)
    elif command == "close":
        print(EVENT_PREFIX + json.dumps({"event": "closed"}), flush=True)
        break
"""


def _fake_worker(tmp_path: Path) -> Path:
    worker = tmp_path / "worker.py"
    worker.write_text(FAKE_WORKER, encoding="utf-8")
    return worker


def test_sd35_generate_many_loads_one_shared_pipeline(tmp_path: Path) -> None:
    worker = _fake_worker(tmp_path)
    generator = LocalSD35ImageGenerator(
        python_executable=sys.executable,
        worker_path=worker,
        timeout_seconds=10,
    )
    results = generator.generate_many(
        [
            ImageGenerationRequest("One mug", tmp_path / "mug"),
            ImageGenerationRequest("One bowl", tmp_path / "bowl"),
        ]
    )

    assert [result.image_path.name for result in results] == [
        "reference.png",
        "reference.png",
    ]
    assert all(result.image_path.is_file() for result in results)
    assert (tmp_path / "loads.txt").read_text(encoding="utf-8") == "1"


def _asset_request(tmp_path: Path, asset_id: str) -> AssetGenerationRequest:
    reference = tmp_path / f"{asset_id}.png"
    reference.write_bytes(b"image")
    return AssetGenerationRequest(
        asset_id=asset_id,
        prompt=f"One {asset_id}",
        target_dimensions=(0.1, 0.1, 0.1),
        reference_images=(reference,),
        output_directory=tmp_path / asset_id,
        mode="image-to-3d",
    )


def test_trellis_generate_many_loads_once_and_uses_isolated_caches(
    tmp_path: Path,
) -> None:
    worker = _fake_worker(tmp_path)
    repo = tmp_path / "TRELLIS"
    (repo / "trellis").mkdir(parents=True)
    provider = LocalTrellisProvider(
        python_executable=sys.executable,
        worker_path=worker,
        repo_dir=repo,
        timeout_seconds=10,
    )
    results = provider.generate_many(
        [_asset_request(tmp_path, "mug"), _asset_request(tmp_path, "bowl")]
    )

    assert all(result.asset_path.read_bytes().startswith(b"glTF") for result in results)
    assert (tmp_path / "loads.txt").read_text(encoding="utf-8") == "1"
    environment = json.loads((tmp_path / "environment.json").read_text(encoding="utf-8"))
    assert environment["PYTHONPATH"].split(":", 1)[0] == str(repo)
    assert "trellis-session-" in environment["NUMBA_CACHE_DIR"]
    assert "trellis-session-" in environment["WARP_CACHE_PATH"]
    assert not Path(environment["NUMBA_CACHE_DIR"]).exists()
    assert not Path(environment["WARP_CACHE_PATH"]).exists()


@pytest.mark.parametrize("worker_module", [sd35_worker, trellis_worker])
def test_worker_serve_loads_pipeline_once_for_multiple_jobs(
    monkeypatch: pytest.MonkeyPatch, worker_module
) -> None:
    calls = {"load": 0, "generate": 0, "release": 0}
    runtime = object()

    def load(config):
        calls["load"] += 1
        assert config == {"model_id": "test-model"}
        return runtime

    def generate(loaded_runtime, request):
        calls["generate"] += 1
        assert loaded_runtime is runtime
        return Path(request["output_path"])

    def release(loaded_runtime):
        calls["release"] += 1
        assert loaded_runtime is runtime

    messages = [
        {"command": "load", "config": {"model_id": "test-model"}},
        {
            "command": "generate",
            "job_id": "first",
            "request": {"output_path": "/tmp/first.output"},
        },
        {
            "command": "generate",
            "job_id": "second",
            "request": {"output_path": "/tmp/second.output"},
        },
        {"command": "close"},
    ]
    standard_input = StringIO("".join(json.dumps(message) + "\n" for message in messages))
    standard_output = StringIO()
    monkeypatch.setattr(worker_module, "_load_pipeline", load)
    monkeypatch.setattr(worker_module, "_generate_one", generate)
    monkeypatch.setattr(worker_module, "_release_pipeline", release)
    monkeypatch.setattr(worker_module.sys, "stdin", standard_input)
    monkeypatch.setattr(worker_module.sys, "stdout", standard_output)

    worker_module._serve()

    events = [
        json.loads(line.removeprefix(worker_module.EVENT_PREFIX))
        for line in standard_output.getvalue().splitlines()
    ]
    assert [event["event"] for event in events] == [
        "ready",
        "completed",
        "completed",
        "closed",
    ]
    assert calls == {"load": 1, "generate": 2, "release": 1}
