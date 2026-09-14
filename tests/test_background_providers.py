import json
from pathlib import Path

from embodied_scene.integrations import (
    AssetGenerationRequest,
    CleanPlateRequest,
    FalImageEditor,
    FalImageGenerator,
    Hunyuan3DProvider,
    ImageGenerationRequest,
    StaticBackgroundRequest,
    WorldLabsProvider,
)


class FakeTransport:
    def __init__(self, responses: list[dict]):
        self.responses = list(responses)
        self.requests = []
        self.downloads = []

    def request_json(self, method, url, *, headers, payload=None):
        self.requests.append((method, url, headers, payload))
        return self.responses.pop(0)

    def download(self, url, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(f"downloaded:{url}".encode())
        self.downloads.append((url, destination))
        return destination


def test_fal_clean_plate_uses_fixed_output_and_removes_state(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    transport = FakeTransport(
        [
            {
                "request_id": "fal-request",
                "status_url": "https://fal.example/status",
                "response_url": "https://fal.example/result",
            },
            {"status": "COMPLETED"},
            {"images": [{"url": "https://cdn.example/clean.png"}]},
        ]
    )
    editor = FalImageEditor(
        provider="gpt-image-2", api_key="secret", transport=transport, sleep=lambda _: None
    )
    result = editor.create_clean_plate(
        CleanPlateRequest(source, "Remove all task entities", tmp_path / "iteration_001")
    )
    assert result.image_path.name == "clean_plate.png"
    assert result.image_path.is_file()
    assert not (result.image_path.parent / ".clean_plate.request.json").exists()
    submitted_payload = transport.requests[0][3]
    assert submitted_payload["image_urls"][0].startswith("data:image/png;base64,")


def test_fal_resumes_without_resubmitting(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    output = tmp_path / "iteration_001"
    output.mkdir()
    (output / ".clean_plate.request.json").write_text(
        json.dumps(
            {
                "provider": "fal",
                "endpoint": "fal-ai/nano-banana-2/edit",
                "request_id": "resume-me",
                "status": "running",
            }
        ),
        encoding="utf-8",
    )
    transport = FakeTransport(
        [
            {"status": "COMPLETED"},
            {"images": [{"url": "https://cdn.example/clean.png"}]},
        ]
    )
    result = FalImageEditor(
        api_key="secret", transport=transport, sleep=lambda _: None
    ).create_clean_plate(CleanPlateRequest(source, "Remove entities", output))
    assert result.image_path.is_file()
    assert all(method == "GET" for method, *_ in transport.requests)


def test_fal_reuses_completed_clean_plate(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    output = tmp_path / "iteration_001"
    output.mkdir()
    (output / "clean_plate.png").write_bytes(b"complete")
    transport = FakeTransport([])
    result = FalImageEditor(api_key="secret", transport=transport).create_clean_plate(
        CleanPlateRequest(source, "Remove entities", output)
    )
    assert result.image_path == output / "clean_plate.png"
    assert transport.requests == []


def test_fal_generates_reference_image_without_source(tmp_path: Path) -> None:
    transport = FakeTransport(
        [
            {"request_id": "image-request"},
            {"status": "COMPLETED"},
            {"images": [{"url": "https://cdn.example/reference.png"}]},
        ]
    )
    result = FalImageGenerator(
        provider="nano-banana", api_key="secret", transport=transport
    ).generate(ImageGenerationRequest("One ceramic mug", tmp_path / "iteration_001"))
    assert result.image_path.name == "reference.png"
    assert result.image_path.is_file()
    assert not (result.image_path.parent / ".reference.request.json").exists()
    method, url, _, payload = transport.requests[0]
    assert method == "POST"
    assert url.endswith("/fal-ai/nano-banana-2")
    assert payload["prompt"] == "One ceramic mug"
    assert "image_urls" not in payload


def test_world_labs_downloads_local_assets_and_removes_state(tmp_path: Path) -> None:
    source = tmp_path / "clean_plate.png"
    source.write_bytes(b"source")
    response = {
        "assets": {
            "splats": {
                "spz_urls": {
                    "full_res": "https://cdn.example/full.spz",
                    "500k": "https://cdn.example/500k.spz",
                }
            },
            "mesh": {"collider_mesh_url": "https://cdn.example/collider.glb"},
            "imagery": {"pano_url": "https://cdn.example/pano.png"},
            "thumbnail_url": "https://cdn.example/thumb.webp",
        }
    }
    transport = FakeTransport(
        [
            {"operation_id": "op-1", "done": False},
            {"operation_id": "op-1", "done": True, "response": response},
        ]
    )
    output = tmp_path / "iteration_001"
    result = WorldLabsProvider(
        api_key="secret", transport=transport, sleep=lambda _: None
    ).generate(StaticBackgroundRequest("demo", "Empty laboratory", source, output))
    assert result.full_resolution_splat == output / "world_full_res.spz"
    assert (output / "world_500k.spz").is_file()
    assert (output / "world_collider.glb").is_file()
    assert (output / "world_pano.png").is_file()
    assert not (output / ".world.request.json").exists()


def test_hunyuan_generates_fixed_candidate_glb(tmp_path: Path) -> None:
    source = tmp_path / "reference.png"
    source.write_bytes(b"source")
    output = tmp_path / "iteration_001"
    transport = FakeTransport(
        [
            {
                "request_id": "asset-request",
                "status_url": "https://fal.example/status",
                "response_url": "https://fal.example/result",
            },
            {"status": "COMPLETED"},
            {
                "model_glb": {
                    "url": "https://cdn.example/model.glb",
                    "content_type": "model/gltf-binary",
                }
            },
        ]
    )
    request = AssetGenerationRequest(
        asset_id="ceramic_mug",
        prompt="One white ceramic mug",
        target_dimensions=(0.11, 0.08, 0.1),
        reference_images=(source,),
        output_directory=output,
        face_count=50_000,
        enable_pbr=True,
        generate_type="Normal",
    )
    result = Hunyuan3DProvider(
        api_key="secret", transport=transport, sleep=lambda _: None
    ).generate(request)
    assert result.asset_path == output / "asset.glb"
    assert result.asset_path.is_file()
    assert not (output / ".asset.request.json").exists()
    payload = transport.requests[0][3]
    assert payload["input_image_url"].startswith("data:image/png;base64,")
    assert payload["face_count"] == 50_000
    assert payload["enable_pbr"] is True
    assert "polygon_type" not in payload
    assert "prompt" not in payload


def test_hunyuan_text_to_3d_sends_prompt_without_image(tmp_path: Path) -> None:
    transport = FakeTransport(
        [
            {"request_id": "asset-request"},
            {"status": "COMPLETED"},
            {"model_glb": {"url": "https://cdn.example/model.glb"}},
        ]
    )
    request = AssetGenerationRequest(
        asset_id="ceramic_mug",
        prompt="One white ceramic mug",
        target_dimensions=(0.11, 0.08, 0.1),
        reference_images=(),
        output_directory=tmp_path / "iteration_001",
        mode="text-to-3d",
    )
    Hunyuan3DProvider(api_key="secret", transport=transport).generate(request)
    _, url, _, payload = transport.requests[0]
    assert url.endswith("/fal-ai/hunyuan3d-v3/text-to-3d")
    assert payload["prompt"] == "One white ceramic mug"
    assert "input_image_url" not in payload


def test_fal_terminal_failure_removes_temporary_state(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    output = tmp_path / "iteration_001"
    transport = FakeTransport(
        [
            {"request_id": "failed-request"},
            {"status": "FAILED"},
        ]
    )
    try:
        FalImageEditor(api_key="secret", transport=transport).edit(
            CleanPlateRequest(source, "Remove entities", output)
        )
    except RuntimeError as error:
        assert "FAILED" in str(error)
    else:
        raise AssertionError("Expected terminal FAL failure")
    assert not (output / ".clean_plate.request.json").exists()


def test_fal_timeout_keeps_only_minimal_resumable_state(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    output = tmp_path / "iteration_001"
    transport = FakeTransport(
        [
            {"request_id": "active-request"},
            {"status": "IN_PROGRESS"},
        ]
    )
    try:
        FalImageEditor(
            api_key="secret", transport=transport, timeout_seconds=0, clock=lambda: 0
        ).edit(CleanPlateRequest(source, "Remove entities", output))
    except TimeoutError:
        pass
    else:
        raise AssertionError("Expected FAL timeout")
    state = json.loads((output / ".clean_plate.request.json").read_text(encoding="utf-8"))
    assert state == {
        "endpoint": "fal-ai/nano-banana-2/edit",
        "request_id": "active-request",
    }


def test_hunyuan_lowpoly_forwards_polygon_type(tmp_path: Path) -> None:
    source = tmp_path / "reference.png"
    source.write_bytes(b"source")
    transport = FakeTransport(
        [
            {"request_id": "asset-request"},
            {"status": "COMPLETED"},
            {"model_glb": {"url": "https://cdn.example/model.glb"}},
        ]
    )
    request = AssetGenerationRequest(
        asset_id="chair",
        prompt="One chair",
        target_dimensions=(0.5, 0.5, 0.9),
        reference_images=(source,),
        output_directory=tmp_path / "out",
        generate_type="LowPoly",
        polygon_type="quadrilateral",
    )
    Hunyuan3DProvider(api_key="secret", transport=transport).generate(request)
    assert transport.requests[0][3]["polygon_type"] == "quadrilateral"


def test_hunyuan_rejects_invalid_face_count_before_submit(tmp_path: Path) -> None:
    source = tmp_path / "reference.png"
    source.write_bytes(b"source")
    transport = FakeTransport([])
    request = AssetGenerationRequest(
        asset_id="chair",
        prompt="One chair",
        target_dimensions=(0.5, 0.5, 0.9),
        reference_images=(source,),
        output_directory=tmp_path / "out",
        face_count=10,
    )
    try:
        Hunyuan3DProvider(api_key="secret", transport=transport).generate(request)
    except ValueError as error:
        assert "face_count" in str(error)
    else:
        raise AssertionError("Expected invalid Hunyuan face count to fail")
    assert transport.requests == []
    assert not (tmp_path / "out" / ".asset.request.json").exists()


def test_world_labs_requires_full_resolution_splat(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    transport = FakeTransport(
        [
            {
                "operation_id": "op-1",
                "done": True,
                "response": {"assets": {"splats": {"spz_urls": {"500k": "https://x/500.spz"}}}},
            }
        ]
    )
    provider = WorldLabsProvider(api_key="secret", transport=transport)
    try:
        provider.generate(StaticBackgroundRequest("demo", "Empty room", source, tmp_path / "out"))
    except RuntimeError as error:
        assert "full_res" in str(error)
    else:
        raise AssertionError("Expected missing full_res SPZ to fail")


def test_world_labs_resumes_partial_download_even_when_full_res_exists(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    output = tmp_path / "iteration_001"
    output.mkdir()
    (output / "world_full_res.spz").write_bytes(b"partial-generation-result")
    (output / ".world.request.json").write_text(
        json.dumps({"provider": "world_labs", "request_id": "resume-op", "status": "running"}),
        encoding="utf-8",
    )
    response = {
        "assets": {
            "splats": {"spz_urls": {"full_res": "https://cdn.example/full.spz"}},
            "imagery": {"pano_url": "https://cdn.example/pano.png"},
        }
    }
    transport = FakeTransport([{"operation_id": "resume-op", "done": True, "response": response}])
    result = WorldLabsProvider(api_key="secret", transport=transport).generate(
        StaticBackgroundRequest("demo", "Empty room", source, output)
    )
    assert result.panorama == output / "world_pano.png"
    assert all(method == "GET" for method, *_ in transport.requests)
    assert not (output / ".world.request.json").exists()
