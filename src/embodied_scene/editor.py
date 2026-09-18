"""Single-workspace local editor. No persistent state beyond scene.yaml/report.json."""

import io
import json
import os
import runpy
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from threading import RLock
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from ruamel.yaml import YAML

from embodied_scene.assembly import default_assembly, validate_assembly, workspace_asset
from embodied_scene.config import load_yaml, repository_root
from embodied_scene.specs.validation import validate_specification
from embodied_scene.usd.delivery import export_scene


def prepare_preview(workspace, temporary, blender):
    physics = load_yaml(workspace / "specs/physics.yaml")
    hidden = []
    for body in physics["bodies"]:
        for collider in body.get("colliders", []):
            if collider.get("hide_visual", False):
                hidden.append(collider["object"])
    settings = temporary / "preview-settings.json"
    settings.write_text(json.dumps({"hidden": hidden}))
    candidate = temporary / "preview-next.glb"
    try:
        result = subprocess.run(
            [
                blender,
                "-b",
                "-noaudio",
                "-t",
                "8",
                str(workspace / "build/scene.blend"),
                "--python-exit-code",
                "1",
                "--python",
                str(repository_root() / "blender_runtime/export_preview.py"),
                "--",
                str(candidate),
                str(settings),
            ],
            stdout=subprocess.PIPE,
            check=False,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=300,
        )
        if result.returncode:
            raise RuntimeError(f"Preview export failed:\n{result.stdout[-2000:]}")
        candidate.replace(temporary / "preview.glb")
    finally:
        settings.unlink(missing_ok=True)
        candidate.unlink(missing_ok=True)


def create_app(workspace: Path, blender: str):
    workspace = workspace.resolve()
    scene_path = workspace / "specs/scene.yaml"
    validate_specification(scene_path, "scene.schema.json")
    lock = RLock()
    pool = ThreadPoolExecutor(max_workers=1)
    scratch = tempfile.TemporaryDirectory(prefix="scene_editor_")
    temporary = Path(scratch.name)
    state = {"text": scene_path.read_text(), "revision": 0, "job": {"status": "idle", "kind": None}}

    @asynccontextmanager
    async def lifespan(app):
        yield
        pool.shutdown(wait=True)
        scratch.cleanup()

    app = FastAPI(lifespan=lifespan)

    @app.middleware("http")
    async def local_requests(request, call_next):
        origin = request.headers.get("origin")
        if origin and urlsplit(origin).hostname not in {"localhost", "127.0.0.1"}:
            return JSONResponse({"detail": "Local editor requests only"}, status_code=403)
        return await call_next(request)

    def preview_choices(spec):
        source = spec.get("world", {}).get("background_asset")
        if not source:
            return []
        choices = [
            Path(source).with_name(f"world_{quality}.spz").as_posix()
            for quality in ("100k", "150k", "500k")
        ]
        choices.append(source)
        configured = spec.get("assembly", {}).get("background", {}).get("preview_asset")
        if configured:
            choices.append(configured)
        return list(dict.fromkeys(p for p in choices if (workspace / p).is_file()))

    def assembly_for(spec):
        if "assembly" in spec:
            return spec["assembly"]
        assembly = default_assembly()
        choices = preview_choices(spec)
        if choices:
            assembly["background"]["preview_asset"] = choices[0]
        return assembly

    def refresh():
        text = scene_path.read_text()
        if text != state["text"]:
            state["text"] = text
            state["revision"] += 1

    def snapshot():
        refresh()
        spec = validate_specification(scene_path, "scene.schema.json")
        assembly = assembly_for(spec)
        validate_assembly(assembly)
        return {
            "name": spec["id"],
            "assembly": assembly,
            "revision": state["revision"],
            "configured": "assembly" in spec,
            "preview_ready": (temporary / "preview.glb").exists(),
            "preview_choices": preview_choices(spec),
        }

    def start_job(kind, operation):
        with lock:
            if state["job"]["status"] == "running":
                raise HTTPException(409, "A build is already running")
            state["job"] = {"status": "running", "kind": kind}

            def run():
                try:
                    operation()
                    result = {"status": "done", "kind": kind}
                except Exception as error:  # noqa: BLE001 - surface worker failures to the UI
                    result = {"status": "error", "kind": kind, "error": str(error)}
                with lock:
                    state["job"] = result

            pool.submit(run)
            return dict(state["job"])

    @app.get("/api/scene")
    def scene():
        with lock:
            return snapshot()

    @app.put("/api/assembly")
    async def save(request: Request):
        try:
            payload = await request.json()
        except ValueError as error:
            raise HTTPException(422, "Expected a JSON object") from error
        if not isinstance(payload, dict):
            raise HTTPException(422, "Expected a JSON object")
        with lock:
            refresh()
            if payload.get("revision") != state["revision"]:
                raise HTTPException(409, "scene.yaml changed; reload before saving")
            if state["job"]["status"] == "running":
                raise HTTPException(409, "Wait for the current build before saving")
            try:
                assembly = validate_assembly(payload["assembly"])
                yaml = YAML()
                document = yaml.load(state["text"])
                if document.get("world", {}).get("background_mode") != "3dgs":
                    raise ValueError("Assembly requires a 3dgs background")
                workspace_asset(workspace, document["world"]["background_asset"])
                preview = assembly["background"].get("preview_asset")
                if preview:
                    workspace_asset(workspace, preview)
                document["assembly"] = assembly
                output = io.StringIO()
                yaml.dump(document, output)
            except Exception as error:
                raise HTTPException(422, str(error)) from error
            # Atomic replace; no backups, hashes, or duplicate scene documents.
            with tempfile.NamedTemporaryFile(
                mode="w", dir=scene_path.parent, suffix=".yaml", delete=False
            ) as file:
                candidate = Path(file.name)
                file.write(output.getvalue())
            try:
                validate_specification(candidate, "scene.schema.json")
                if scene_path.read_text() != state["text"]:
                    raise HTTPException(409, "scene.yaml changed during save; reload")
                os.replace(candidate, scene_path)
            finally:
                candidate.unlink(missing_ok=True)
            return snapshot()

    @app.get("/api/assets/{asset_id}")
    def asset(asset_id: str, source: str | None = None):
        if asset_id == "interactive":
            path = temporary / "preview.glb"
        else:
            spec = load_yaml(scene_path)
            world = spec.get("world", {})
            choices = {
                "background": assembly_for(spec)
                .get("background", {})
                .get("preview_asset", world.get("background_asset")),
                "reference": world.get("background_input"),
            }
            relative = choices.get(asset_id)
            if asset_id == "background" and source and source != "default":
                if source not in preview_choices(spec):
                    raise HTTPException(404, "Unknown background preview")
                relative = source
            if not relative:
                raise HTTPException(404, "Unknown asset")
            try:
                path = workspace_asset(workspace, relative)
            except ValueError as error:
                raise HTTPException(404, str(error)) from error
        if not path.is_file():
            raise HTTPException(404, "Preview has not been prepared")
        return FileResponse(path, headers={"Cache-Control": "no-store"})

    @app.post("/api/preview")
    def preview():
        return start_job("preview", lambda: prepare_preview(workspace, temporary, blender))

    @app.post("/api/estimate-floor")
    def estimate_background_floor(payload: dict):
        from usd_convert_gsplat import read_spz

        from embodied_scene.floor import estimate_floor

        with lock:
            refresh()
            if payload.get("revision") != state["revision"]:
                raise HTTPException(409, "scene.yaml changed; reload before estimating")
            if state["job"]["status"] == "running":
                raise HTTPException(409, "Wait for the current build")
            try:
                assembly = validate_assembly(payload["assembly"])
                spec = load_yaml(scene_path)
                if spec.get("world", {}).get("background_mode") != "3dgs":
                    raise ValueError("Requires a 3dgs background")
                # Estimate the same resolution displayed in the editor.
                relative = assembly["background"].get("preview_asset") or spec["world"]["background_asset"]
                if relative not in preview_choices(spec):
                    raise ValueError("Unknown background preview")
                path = workspace_asset(workspace, relative)
            except Exception as error:
                raise HTTPException(422, str(error)) from error
        try:
            return estimate_floor(read_spz(str(path)), assembly)
        except Exception as error:
            raise HTTPException(422, str(error)) from error

    @app.post("/api/export")
    def export():
        with lock:
            if "assembly" not in load_yaml(scene_path):
                raise HTTPException(422, "Save assembly before exporting")

        def operation():
            # Preserve the existing workspace's explicit USD lighting/display policy.
            settings = workspace / "source/usd_settings.py"
            configure = (
                runpy.run_path(str(settings)).get("configure_stage") if settings.exists() else None
            )
            result = export_scene(
                workspace / "build/scene.blend",
                workspace / "specs/physics.yaml",
                workspace,
                blender=blender,
                configure_stage=configure,
            )
            if result["status"] != "pass":
                raise ValueError("; ".join(result["errors"]))

        return start_job("export", operation)

    @app.get("/api/job")
    def job():
        with lock:
            return dict(state["job"])

    # Same-origin API in production; Vite proxies /api during development.
    frontend = repository_root() / "apps/scene-editor/dist"
    if frontend.exists():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="editor")
    return app
