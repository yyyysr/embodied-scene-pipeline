"""Preserve Blender orthographic cameras unsupported by its USD exporter."""

from pxr import Gf, UsdGeom


def author_orthographic_cameras(stage, records):
    for record in records:
        config = record.get("orthographic_camera")
        if config is None:
            continue
        matches = [p for p in stage.Traverse() if p.GetName() == record["export_name"]]
        if len(matches) != 1:
            raise ValueError(f"Cannot locate camera {record['export_name']}")
        parent = matches[0]
        path = parent.GetPath().AppendChild(record["export_name"] + "_geometry")
        camera = UsdGeom.Camera.Define(stage, path)
        camera.CreateProjectionAttr(UsdGeom.Tokens.orthographic)
        aspect = config["aspect"]
        width = config["scale"] * min(aspect, 1.0)
        height = config["scale"] / max(aspect, 1.0)
        # USD apertures are in tenths of a scene unit; scene units are meters.
        camera.CreateHorizontalApertureAttr(width * 10.0)
        camera.CreateVerticalApertureAttr(height * 10.0)
        camera.CreateHorizontalApertureOffsetAttr(config["shift_x"] * config["scale"] * 10.0)
        camera.CreateVerticalApertureOffsetAttr(config["shift_y"] * config["scale"] * 10.0)
        camera.CreateClippingRangeAttr(Gf.Vec2f(config["clip_start"], config["clip_end"]))
