from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
Image = pytest.importorskip("PIL.Image")
ImageDraw = pytest.importorskip("PIL.ImageDraw")
pytest.importorskip("cv2")

from local_runtime.trellis_worker import _prepare_image


def test_trellis_white_background_preprocess_preserves_white_object_interior(
    tmp_path: Path,
) -> None:
    source = Image.new("RGB", (256, 256), "white")
    draw = ImageDraw.Draw(source)
    draw.ellipse((64, 48, 192, 208), fill="white", outline="black", width=6)
    path = tmp_path / "reference.png"
    source.save(path)

    processed = np.asarray(_prepare_image(path))
    assert processed.shape == (518, 518, 3)
    assert np.all(processed[259, 259] > 240)
    assert np.all(processed[0, 0] < 5)


def test_trellis_preprocess_rejects_nonuniform_opaque_border(tmp_path: Path) -> None:
    pixels = np.zeros((128, 128, 3), dtype=np.uint8)
    pixels[:, :64] = (255, 255, 255)
    pixels[:, 64:] = (40, 80, 120)
    path = tmp_path / "reference.png"
    Image.fromarray(pixels).save(path)

    try:
        _prepare_image(path)
    except ValueError as error:
        assert "stable white border" in str(error)
    else:
        raise AssertionError("Expected a nonuniform opaque border to fail")
