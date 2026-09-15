import json
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from scripts import generate_local_batch


class _Session:
    def __init__(self, generated: list) -> None:
        self.generated = generated
        self.entered = 0

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, *_args) -> None:
        return None

    def generate(self, request):
        self.generated.append(request)
        if hasattr(request, "output_filename"):
            path = request.output_directory / request.output_filename
            return SimpleNamespace(image_path=path)
        return SimpleNamespace(asset_path=request.output_directory / "asset.glb")


class _Provider:
    def __init__(self) -> None:
        self.generated = []
        self.shared_session = _Session(self.generated)

    def session(self) -> _Session:
        return self.shared_session


def _events(output: StringIO) -> list[dict]:
    return [json.loads(line) for line in output.getvalue().splitlines()]


def test_sd35_jsonl_batch_uses_one_session_and_streams_results(
    monkeypatch, tmp_path: Path
) -> None:
    provider = _Provider()
    monkeypatch.setattr(generate_local_batch, "_sd35_provider", lambda _defaults: provider)
    input_stream = StringIO(
        "\n".join(
            [
                json.dumps(
                    {
                        "job_id": "mug",
                        "prompt": "One mug",
                        "output_path": str(tmp_path / "mug.png"),
                    }
                ),
                json.dumps(
                    {
                        "job_id": "bowl",
                        "prompt": "One bowl",
                        "output_path": str(tmp_path / "bowl.png"),
                    }
                ),
            ]
        )
    )
    output = StringIO()

    status = generate_local_batch.main(
        ["--provider", "sd35"], input_stream=input_stream, output_stream=output
    )

    assert status == 0
    assert provider.shared_session.entered == 1
    assert [request.prompt for request in provider.generated] == ["One mug", "One bowl"]
    assert _events(output) == [
        {
            "status": "completed",
            "provider": "sd35",
            "job_id": "mug",
            "output_path": str(tmp_path / "mug.png"),
        },
        {
            "status": "completed",
            "provider": "sd35",
            "job_id": "bowl",
            "output_path": str(tmp_path / "bowl.png"),
        },
    ]


def test_trellis_jsonl_batch_uses_one_session(monkeypatch, tmp_path: Path) -> None:
    provider = _Provider()
    monkeypatch.setattr(
        generate_local_batch, "_trellis_provider", lambda _defaults: provider
    )
    mug_reference = tmp_path / "mug.png"
    bowl_reference = tmp_path / "bowl.png"
    mug_reference.write_bytes(b"image")
    bowl_reference.write_bytes(b"image")
    input_stream = StringIO(
        "\n".join(
            [
                json.dumps(
                    {
                        "job_id": "mug",
                        "prompt": "One mug",
                        "input_path": str(mug_reference),
                        "output_path": str(tmp_path / "mug" / "asset.glb"),
                        "target_dimensions": [0.11, 0.08, 0.1],
                    }
                ),
                json.dumps(
                    {
                        "job_id": "bowl",
                        "prompt": "One bowl",
                        "input_path": str(bowl_reference),
                        "output_path": str(tmp_path / "bowl" / "asset.glb"),
                        "target_dimensions": [0.15, 0.15, 0.07],
                    }
                ),
            ]
        )
    )
    output = StringIO()

    status = generate_local_batch.main(
        ["--provider", "trellis"], input_stream=input_stream, output_stream=output
    )

    assert status == 0
    assert provider.shared_session.entered == 1
    assert [request.asset_id for request in provider.generated] == ["mug", "bowl"]
    assert [event["job_id"] for event in _events(output)] == ["mug", "bowl"]


def test_batch_validates_every_job_before_starting_model(monkeypatch, tmp_path: Path) -> None:
    provider = _Provider()
    monkeypatch.setattr(generate_local_batch, "_sd35_provider", lambda _defaults: provider)
    input_stream = StringIO(
        "\n".join(
            [
                json.dumps(
                    {
                        "job_id": "valid",
                        "prompt": "One mug",
                        "output_path": str(tmp_path / "mug.png"),
                    }
                ),
                json.dumps(
                    {
                        "job_id": "invalid",
                        "prompt": "",
                        "output_path": str(tmp_path / "invalid.png"),
                    }
                ),
            ]
        )
    )
    output = StringIO()

    status = generate_local_batch.main(
        ["--provider", "sd35"], input_stream=input_stream, output_stream=output
    )

    assert status == 1
    assert provider.shared_session.entered == 0
    assert _events(output)[0]["status"] == "error"
