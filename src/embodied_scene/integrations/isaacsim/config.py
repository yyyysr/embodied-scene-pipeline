"""Host-side semantic checks, independent of Isaac Sim."""

import math
from pathlib import Path

from embodied_scene.specs.validation import validate_specification


def validate_config(config):
    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Isaac Sim values must be finite")
        if isinstance(value, dict):
            for child in value.values():
                finite(child)
        elif isinstance(value, list):
            for child in value:
                finite(child)

    finite(config)
    ids, roots = set(), set()
    for body in config["deformables"]:
        if body["id"] in ids or body["object"] in roots:
            raise ValueError("Duplicate deformable ID or object")
        ids.add(body["id"])
        roots.add(body["object"])
        mat = config["materials"].get(body["material"])
        if mat is None:
            raise ValueError(f"Unknown deformable material: {body['material']}")
        if "mass_kg" not in body and "density_kg_m3" not in mat:
            raise ValueError("Each deformable requires mass_kg or material density_kg_m3")
        surface = body["kind"] == "surface"
        if surface and not {"surface_thickness_m", "bend_stiffness_pa"} <= mat.keys():
            raise ValueError("Surface material requires thickness and explicit bend policy")
        if not surface and any(
            k in mat for k in ("surface_thickness_m", "bend_stiffness_pa", "bend_damping_per_s")
        ):
            raise ValueError("Surface material cannot be assigned to a volume deformable")
        if not surface and "rest_bend" in body:
            raise ValueError("rest_bend is surface-only")
        if not surface and any(body.get("initial_velocity_m_s", [0, 0, 0])):
            raise ValueError("Deferred volume generation requires zero initial velocity")
        if surface and body.get("cooking"):
            raise ValueError("Volume cooking options cannot be used for a surface")
        contact = body["contact"]
        if contact["contact_offset_m"] <= contact["rest_offset_m"]:
            raise ValueError("contact_offset_m must exceed rest_offset_m")
        distance = contact.get("self_collision_filter_distance_m", "auto")
        if distance != "auto" and distance < 2 * contact["rest_offset_m"]:
            raise ValueError("Self-collision filter distance must be >= 2 * rest offset")
        solver = body.get("solver", {})
        iterations = solver.get("position_iterations", 16)
        frequency = solver.get("collision_pair_update_frequency", 1)
        if frequency != "auto" and frequency > iterations:
            raise ValueError("Collision pair frequency exceeds position iterations")
        multiplier = solver.get("collision_iteration_multiplier")
        if multiplier is not None and multiplier > iterations // 2:
            raise ValueError("Collision multiplier exceeds half the position iterations")
        if not surface and (
            any(
                k in solver
                for k in ("collision_pair_update_frequency", "collision_iteration_multiplier")
            )
            or solver.get("max_linear_velocity_m_s") == "auto"
        ):
            raise ValueError("Surface-only solver setting on volume deformable")
    attachment_ids = set()
    for attachment in config.get("attachments", []):
        if attachment["id"] in attachment_ids:
            raise ValueError("Duplicate attachment ID")
        attachment_ids.add(attachment["id"])
        if attachment["body"] not in ids:
            raise ValueError("Unknown attachment body")
        body = next(b for b in config["deformables"] if b["id"] == attachment["body"])
        if body["kind"] != "surface":
            raise ValueError("Node attachments require an explicit surface simulation mesh")
        if attachment["target"] in roots:
            raise ValueError("Deformable-to-deformable attachment is outside initial support")
        region = attachment["region"]
        if any(a >= b for a, b in zip(region["min"], region["max"])):
            raise ValueError("Attachment region must have positive extent")
    return config


def load_extension(physics_path: Path):
    physics = validate_specification(physics_path, "physics.schema.json")
    relative = physics.get("extensions", {}).get("isaacsim")
    if relative is None:
        return None
    base = physics_path.resolve().parent
    path = (base / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(base):
        raise ValueError("Isaac Sim extension must be a relative file inside specs/")
    return validate_config(validate_specification(path, "isaacsim.schema.json"))


def ownership_paths(config, stage, mapping, occupied=()):
    from pxr import Sdf, Usd, UsdGeom

    paths = []
    for body in config["deformables"]:
        path = Sdf.Path(mapping[body["object"]])
        prim = stage.GetPrimAtPath(path)
        if not prim or prim.GetTypeName() != "Xform":
            raise ValueError(f"Deformable root must be an Xform: {path}")
        if any(path.HasPrefix(p) or p.HasPrefix(path) for p in [*occupied, *paths]):
            raise ValueError(f"Overlapping physics ownership: {path}")
        source = Sdf.Path(mapping[body["source_mesh"]])
        if source == path or not source.HasPrefix(path):
            raise ValueError("Source mesh must be inside its deformable root")
        meshes = [p for p in Usd.PrimRange(stage.GetPrimAtPath(source)) if p.IsA(UsdGeom.Mesh)]
        if len(meshes) != 1:
            raise ValueError("source_mesh must resolve to exactly one mesh")
        paths.append(path)
    for attachment in config.get("attachments", []):
        target = Sdf.Path(mapping[attachment["target"]])
        if any(target.HasPrefix(p) or p.HasPrefix(target) for p in paths):
            raise ValueError("Attachment target must be independent of deformable roots")
        if not stage.GetPrimAtPath(target).IsA(UsdGeom.Xformable):
            raise ValueError("Attachment target must be Xformable")
    return paths
