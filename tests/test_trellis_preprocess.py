from pathlib import Path

import pytest

Image = pytest.importorskip("PIL.Image")

from local_runtime.trellis_worker import _generate_one


class _Pipeline:
    def __init__(self) -> None:
        self.calls = []

    def run(self, image, **kwargs):
        self.calls.append((image, kwargs))
        return {"gaussian": ["gaussian"], "mesh": ["mesh"]}


class _Glb:
    def export(self, path: str) -> None:
        Path(path).write_bytes(b"glTF generated")


class _Postprocessing:
    def to_glb(self, gaussian, mesh, **kwargs):
        assert (gaussian, mesh) == ("gaussian", "mesh")
        assert kwargs == {"simplify": 0.95, "texture_size": 1024, "verbose": False}
        return _Glb()


@pytest.mark.parametrize("mode", ["RGB", "RGBA"])
def test_trellis_run_delegates_preprocessing_to_pipeline(
    tmp_path: Path, mode: str
) -> None:
    input_path = tmp_path / "reference.png"
    color = "white" if mode == "RGB" else (255, 255, 255, 0)
    Image.new(mode, (256, 128), color).save(input_path)
    output_path = tmp_path / "asset.glb"
    pipeline = _Pipeline()

    result = _generate_one(
        (pipeline, _Postprocessing()),
        {
            "input_path": str(input_path),
            "output_path": str(output_path),
            "seed": 42,
            "sparse_structure_steps": 12,
            "sparse_structure_guidance": 7.5,
            "slat_steps": 12,
            "slat_guidance": 3.0,
            "simplify": 0.95,
            "texture_size": 1024,
        },
    )

    assert result == output_path
    assert output_path.read_bytes() == b"glTF generated"
    image, options = pipeline.calls[0]
    assert image.mode == mode
    assert image.size == (256, 128)
    assert options["preprocess_image"] is True
    assert options["formats"] == ["mesh", "gaussian"]
