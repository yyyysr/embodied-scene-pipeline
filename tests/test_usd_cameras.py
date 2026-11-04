import pytest
from pxr import Usd, UsdGeom

from embodied_scene.usd.cameras import author_orthographic_cameras


@pytest.mark.parametrize(
    ("aspect", "expected_width", "expected_height"),
    [(2.0, 6.0, 3.0), (0.5, 3.0, 6.0)],
)
def test_orthographic_camera_aperture_and_clipping(aspect, expected_width, expected_height):
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World/review_camera")
    author_orthographic_cameras(stage, [{
        "export_name": "review_camera",
        "orthographic_camera": {
            "scale": 0.6, "aspect": aspect, "shift_x": 0, "shift_y": 0,
            "clip_start": 0.01, "clip_end": 100.0,
        },
    }])
    camera = UsdGeom.Camera.Get(stage, "/World/review_camera/review_camera_geometry")
    assert camera.GetProjectionAttr().Get() == UsdGeom.Tokens.orthographic
    assert camera.GetHorizontalApertureAttr().Get() == pytest.approx(expected_width)
    assert camera.GetVerticalApertureAttr().Get() == pytest.approx(expected_height)
    assert list(camera.GetClippingRangeAttr().Get()) == pytest.approx([0.01, 100.0])
