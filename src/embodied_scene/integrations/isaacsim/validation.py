"""Validate the authored representation using ordinary OpenUSD."""

import math

import numpy as np
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade

from .attachments import selection
from .authoring import body_values
from .config import ownership_paths, validate_config
from .materials import expected_values
from .meshes import mesh_for, triangles
from .schema import TYPES, has_api


def compare(prim, values):
    for name, expected in values.items():
        attr = prim.GetAttribute(name)
        value = attr.Get()
        if attr.GetTypeName() != TYPES[name] or value is None:
            raise ValueError(f"Missing/wrongly typed attribute: {prim.GetPath()}.{name}")
        equal = (
            value == expected
            if isinstance(expected, str)
            else math.isclose(value, expected, rel_tol=1e-5, abs_tol=1e-8)
        )
        if not equal:
            raise ValueError(f"Attribute differs from specification: {prim.GetPath()}.{name}")


def require_api(prim, *schemas):
    for schema in schemas:
        if not has_api(prim, schema):
            raise ValueError(f"Missing API {schema}: {prim.GetPath()}")


def check_pose(prim, points=None):
    require_api(prim, "OmniPhysicsDeformablePoseAPI:default")
    for name in ("deformablePose:default:omniphysics:purposes",):
        if prim.GetAttribute(name).GetTypeName() != TYPES[name]:
            raise ValueError("Invalid bind pose attribute type")
    if list(prim.GetAttribute("deformablePose:default:omniphysics:purposes").Get() or []) != [
        "bindPose"
    ]:
        raise ValueError("Missing bind pose purpose")
    if points is not None:
        if (
            prim.GetAttribute("deformablePose:default:omniphysics:points").GetTypeName()
            != TYPES["deformablePose:default:omniphysics:points"]
        ):
            raise ValueError("Invalid bind points type")
        bind = np.asarray(prim.GetAttribute("deformablePose:default:omniphysics:points").Get())
        points = np.asarray(points)
        if (
            bind.shape != points.shape
            or not np.isfinite(bind).all()
            or not np.allclose(bind, points)
        ):
            raise ValueError(f"Invalid bind pose: {prim.GetPath()}")


def validate(stage, config, mapping):
    from embodied_scene.usd.pipeline import rigid_transform

    validate_config(config)
    ownership_paths(config, stage, mapping)
    scene = stage.GetPrimAtPath("/World/Physics/Scene")
    require_api(scene, "PhysxSceneAPI")
    compare(
        scene,
        {
            "physxScene:enableGPUDynamics": True,
            "physxScene:broadphaseType": "GPU",
            "physxScene:timeStepsPerSecond": config.get("scene", {}).get(
                "time_steps_per_second", 120
            ),
        },
    )
    counts = {"volume": 0, "surface": 0, "attachments": 0}
    bodies = {}
    for spec in config["deformables"]:
        root = stage.GetPrimAtPath(mapping[spec["object"]])
        rigid_transform(stage, root.GetPath())
        require_api(root, "OmniPhysicsDeformableBodyAPI", "PhysxBaseDeformableBodyAPI")
        compare(root, body_values(spec))
        if root.GetRelationship("omniphysics:simulationOwner").GetTargets() != [scene.GetPath()]:
            raise ValueError("Invalid simulation owner")
        source = mesh_for(stage, mapping[spec["source_mesh"]])
        triangles(source, closed=spec["kind"] == "volume")
        sim = stage.GetPrimAtPath(root.GetPath().AppendChild("SimulationMesh"))
        require_api(sim, "OmniPhysics" + spec["kind"].title() + "DeformableSimAPI")
        collider = sim
        generated = set()
        if spec["kind"] == "volume":
            require_api(root, "PhysxAutoDeformableBodyAPI")
            compare(root, {"physxDeformableBody:autoDeformableBodyEnabled": True})
            if root.GetRelationship("physxDeformableBody:cookingSourceMesh").GetTargets() != [
                source.GetPath()
            ]:
                raise ValueError("Invalid cooking source")
            resolution = spec.get("cooking", {}).get("volume_hex_resolution")
            if resolution:
                require_api(root, "PhysxAutoDeformableHexahedralMeshAPI")
                compare(root, {"physxDeformableBody:resolution": resolution})
                collider = stage.GetPrimAtPath(root.GetPath().AppendChild("CollisionMesh"))
            generated = {sim, collider}
            for prim in generated:
                if not prim or prim.GetTypeName() != "TetMesh":
                    raise ValueError("Missing TetMesh declaration")
                if (
                    prim.GetAttribute("points").Get() is not None
                    or prim.GetAttribute("tetVertexIndices").Get() is not None
                ):
                    raise ValueError("Expected deferred volume geometry")
                check_pose(prim)
        else:
            require_api(root, "PhysxSurfaceDeformableBodyAPI")
            points, indices = triangles(UsdGeom.Mesh(sim))
            rest = np.asarray(sim.GetAttribute("omniphysics:restShapePoints").Get())
            rest_indices = np.asarray(sim.GetAttribute("omniphysics:restTriVtxIndices").Get())
            vel = np.asarray(UsdGeom.PointBased(sim).GetVelocitiesAttr().Get())
            if rest.shape != points.shape or not np.allclose(rest, points):
                raise ValueError("Invalid surface rest points")
            if not np.array_equal(indices, rest_indices):
                raise ValueError("Invalid surface rest topology")
            if (
                vel.shape != points.shape
                or not np.isfinite(vel).all()
                or not np.allclose(vel, spec.get("initial_velocity_m_s", [0, 0, 0]))
            ):
                raise ValueError("Invalid surface velocities")
            # Simulation positions must remain in the declared source frame.
            cache = UsdGeom.XformCache()
            transform = (
                cache.GetLocalToWorldTransform(source.GetPrim())
                * cache.GetLocalToWorldTransform(root).GetInverse()
            )
            expected = [transform.Transform(p) for p in source.GetPointsAttr().Get()]
            if not np.allclose(points, expected) or not np.array_equal(
                indices.ravel(), source.GetFaceVertexIndicesAttr().Get()
            ):
                raise ValueError("Simulation differs from source")
            compare(
                sim, {"omniphysics:restBendAnglesDefault": spec.get("rest_bend", "flatDefault")}
            )
        colliders = [p for p in Usd.PrimRange(root) if p.HasAPI(UsdPhysics.CollisionAPI)]
        if colliders != [collider]:
            raise ValueError("Expected one owned collider")
        for prim in {sim, collider}:
            if UsdGeom.Imageable(prim).GetPurposeAttr().Get() != "guide":
                raise ValueError("Simulation/collision geometry requires guide purpose")
        require_api(collider, "PhysxCollisionAPI")
        compare(
            collider,
            {
                "physxCollision:restOffset": spec["contact"]["rest_offset_m"],
                "physxCollision:contactOffset": spec["contact"]["contact_offset_m"],
            },
        )
        for prim in {root, sim, collider}:
            mat, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial("physics")
            if not mat or mat.GetPath() != "/World/Physics/DeformableMaterials/" + spec["material"]:
                raise ValueError("Incorrect effective physics material")
            require_api(
                mat.GetPrim(), "OmniPhysicsDeformableMaterialAPI", "PhysxDeformableMaterialAPI"
            )
            if spec["kind"] == "surface":
                require_api(
                    mat.GetPrim(),
                    "OmniPhysicsSurfaceDeformableMaterialAPI",
                    "PhysxSurfaceDeformableMaterialAPI",
                )
            compare(mat.GetPrim(), expected_values(config["materials"][spec["material"]]))
        for prim in Usd.PrimRange(root):
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                raise ValueError("Rigid body nested in deformable")
            if prim not in generated and prim.IsA(UsdGeom.PointBased):
                check_pose(prim, UsdGeom.PointBased(prim).GetPointsAttr().Get())
        counts[spec["kind"]] += 1
        bodies[spec["id"]] = (root, sim)
    for spec in config.get("attachments", []):
        prim = stage.GetPrimAtPath("/World/Physics/DeformableAttachments/" + spec["id"])
        root, sim = bodies[spec["body"]]
        target = stage.GetPrimAtPath(mapping[spec["target"]])
        if not prim or prim.GetTypeName() != "OmniPhysicsVtxXformAttachment":
            raise ValueError("Missing attachment")
        if prim.GetRelationship("omniphysics:src0").GetTargets() != [
            root.GetPath()
        ] or prim.GetRelationship("omniphysics:src1").GetTargets() != [target.GetPath()]:
            raise ValueError("Invalid attachment references")
        ids, positions = selection(stage, root, sim, target, spec["region"])
        actual = np.asarray(prim.GetAttribute("omniphysics:localPositionsSrc1").Get())
        if (
            list(prim.GetAttribute("omniphysics:vtxIndicesSrc0").Get() or []) != ids
            or actual.shape != np.asarray(positions).shape
            or not np.allclose(actual, positions)
        ):
            raise ValueError("Invalid attachment selection/frame")
        counts["attachments"] += 1
    return counts


def validate_file(path, config, mapping):
    stage = Usd.Stage.Open(str(path))
    if not stage:
        raise ValueError("Cannot reopen delivery USD")
    return {
        "status": "pass",
        "counts": validate(stage, config, mapping),
        "profile": config["runtime"]["profile"],
        "authoring": "offline",
        "volume_mesh_generation": "deferred"
        if any(b["kind"] == "volume" for b in config["deformables"])
        else "not_required",
    }
