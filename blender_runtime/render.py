from __future__ import annotations

from pathlib import Path

import bpy


def configure_render() -> None:
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 480
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"


def render_views(cameras: dict[str, object], output_directory: Path) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    configure_render()
    ceilings = [obj for obj in bpy.data.objects if obj.name.startswith("ceiling_")]
    previous_visibility = {obj.name: obj.hide_render for obj in ceilings}
    try:
        for obj in ceilings:
            obj.hide_render = True
        for view, camera in cameras.items():
            bpy.context.scene.camera = camera
            bpy.context.scene.render.filepath = str(output_directory / f"{view}.png")
            bpy.ops.render.render(write_still=True)
        if "task" in cameras:
            _render_articulation_view(cameras["task"], output_directory)
    finally:
        for obj in ceilings:
            obj.hide_render = previous_visibility[obj.name]


def _render_articulation_view(camera, output_directory: Path) -> None:
    """Render representative open states, then restore the closed delivery state."""
    scene = bpy.context.scene
    scene.camera = camera
    states = []

    def set_rotation(name: str, value: float) -> None:
        obj = bpy.data.objects.get(name)
        if obj is not None:
            states.append((obj, "rotation_euler", obj.rotation_euler.copy()))
            obj.rotation_euler[2] = value

    def set_local_y(name: str, delta: float) -> None:
        obj = bpy.data.objects.get(name)
        if obj is not None:
            states.append((obj, "location", obj.location.copy()))
            obj.location.y += delta

    set_rotation("master_bathroom_door", -1.5708)
    set_local_y("service_balcony_door_leaf_slide", 0.78)
    for index in (1, 2, 3):
        set_local_y(f"kitchen_drawer_{index}_slide", 0.38)
    set_local_y("living_tv_console_drawer_002_slide", -0.36)
    bpy.context.view_layer.update()
    scene.render.filepath = str(output_directory / "articulation_open.png")
    bpy.ops.render.render(write_still=True)
    for obj, attribute, value in reversed(states):
        setattr(obj, attribute, value)
    bpy.context.view_layer.update()
