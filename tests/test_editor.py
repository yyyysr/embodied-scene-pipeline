import copy

import pytest
import yaml

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from embodied_scene.assembly import default_assembly
from embodied_scene.editor import create_app


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "specs").mkdir()
    (tmp_path / "generated_assets/backgrounds").mkdir(parents=True)
    (tmp_path / "generated_assets/backgrounds/world.spz").touch()
    spec = {
        "id": "test",
        "environment": "tabletop",
        "objects": [],
        "world": {
            "background_mode": "3dgs",
            "background_asset": "generated_assets/backgrounds/world.spz",
            "background_input": "input/references/bg.png",
            "background_decision": "use_reference_directly",
        },
    }
    (tmp_path / "specs/scene.yaml").write_text("# Keep this comment\n" + yaml.safe_dump(spec))
    return tmp_path


def test_save_roundtrip_conflict_and_no_sidecars(workspace):
    with TestClient(create_app(workspace, "blender")) as client:
        original = client.get("/api/scene").json()
        assembly = default_assembly()
        assembly["background"]["placement"]["position_m"] = [1, 2, 3]
        result = client.put(
            "/api/assembly", json={"revision": original["revision"], "assembly": assembly}
        )
        assert result.status_code == 200, result.text
        assert result.json()["assembly"] == assembly
        assert "# Keep this comment" in (workspace / "specs/scene.yaml").read_text()
        assert list((workspace / "specs").iterdir()) == [workspace / "specs/scene.yaml"]
        assert (
            client.put(
                "/api/assembly", json={"revision": original["revision"], "assembly": assembly}
            ).status_code
            == 409
        )
        assert client.get("/api/assets/unknown").status_code == 404
        assert client.get("/api/assets/background").status_code == 200
        assert client.get("/api/assets/background?source=../outside.spz").status_code == 404
        assert (
            client.post("/api/preview", headers={"Origin": "https://example.com"}).status_code
            == 403
        )
        revision = result.json()["revision"]
        with (workspace / "specs/scene.yaml").open("a") as file:
            file.write("# External edit\n")
        assert (
            client.put(
                "/api/assembly", json={"revision": revision, "assembly": assembly}
            ).status_code
            == 409
        )


def test_invalid_save_preserves_file(workspace):
    before = (workspace / "specs/scene.yaml").read_text()
    with TestClient(create_app(workspace, "blender")) as client:
        scene = client.get("/api/scene").json()
        for change in ("quaternion", "scale", "path"):
            assembly = copy.deepcopy(scene["assembly"])
            if change == "quaternion":
                assembly["background"]["placement"]["orientation_xyzw"] = [0, 0, 0, 0]
            elif change == "scale":
                assembly["background"]["placement"]["uniform_scale"] = -1
            else:
                assembly["background"]["preview_asset"] = "../outside.spz"
            result = client.put(
                "/api/assembly", json={"revision": scene["revision"], "assembly": assembly}
            )
            assert result.status_code == 422
        assert (workspace / "specs/scene.yaml").read_text() == before
