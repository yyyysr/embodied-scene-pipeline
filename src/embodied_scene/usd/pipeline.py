from __future__ import annotations

import json
import math
from pathlib import Path

import jsonschema
from pxr import Gf, Sdf, Tf, Usd, UsdGeom, UsdLux, UsdPhysics, UsdShade, UsdUtils

from embodied_scene.specs.validation import validate_specification


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def build_object_map(exports: Path, *, debug: bool = False) -> dict:
    stage = Usd.Stage.Open(str(exports / "geometry.usdc"))
    if not stage:
        raise ValueError("Cannot open geometry.usdc")
    records = json.loads((exports / "blender_objects.json").read_text())["objects"]
    mapping = {}
    errors = []
    checked_meshes = 0
    for record in records:
        object_id = record.get("reference_id") or record.get("semantic_id")
        candidates = [p for p in stage.Traverse() if p.GetName() == record["export_name"]]
        if len(candidates) != 1:
            raise ValueError(f"Expected one exported object for {record['export_name']}")
        if "world_bounds" in record:
            points = []
            cache = UsdGeom.XformCache()
            for prim in Usd.PrimRange(candidates[0]):
                if prim.IsA(UsdGeom.Mesh):
                    transform = cache.GetLocalToWorldTransform(prim)
                    points.extend(
                        transform.Transform(Gf.Vec3d(*p))
                        for p in UsdGeom.Mesh(prim).GetPointsAttr().Get()
                    )
            # Mesh objects with mesh children are unsupported for exact bounds comparison.
            if not points:
                errors.append(f"Missing mesh points: {record['export_name']}")
            else:
                actual = [
                    [min(p[i] for p in points) for i in range(3)],
                    [max(p[i] for p in points) for i in range(3)],
                ]
                if any(
                    abs(a - b) > 1e-4
                    for row, ref in zip(actual, record["world_bounds"])
                    for a, b in zip(row, ref)
                ):
                    errors.append(f"World bounds mismatch: {record['blender_name']}")
            checked_meshes += 1
        if not object_id:
            continue
        if object_id in mapping:
            raise ValueError(f"Duplicate object ID: {object_id}")
        mapping[object_id] = str(candidates[0].GetPath())
    if UsdGeom.GetStageUpAxis(stage) != "Z" or UsdGeom.GetStageMetersPerUnit(stage) != 1:
        errors.append("Geometry must be meters and Z-up")
    if errors:
        raise ValueError("; ".join(errors))
    print(f"Export checked: {checked_meshes} mesh bounds, {len(records)} objects")
    result = {"objects": mapping}
    if debug:
        write_json(exports / "object_map.json", result)
    return result


def semantic_object_map(stage):
    """Resolve fresh paths from the actual USD, never a saved mapping or hash."""
    mapping = {}
    ambiguous = set()
    for prim in stage.Traverse():
        name = prim.GetName()
        if name in mapping:
            ambiguous.add(name)
        else:
            mapping[name] = str(prim.GetPath())
    for name in ambiguous:
        del mapping[name]
    return mapping


def rigid_transform(stage, path):
    matrix = UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(path))
    axes = [Gf.Vec3d(*matrix[i][:3]) for i in range(3)]
    if (
        any(abs(v.GetLength() - 1) > 1e-5 for v in axes)
        or any(abs(Gf.Dot(axes[i], axes[j])) > 1e-5 for i in range(3) for j in range(i))
        or matrix.GetDeterminant() < 0
    ):
        raise ValueError(f"Body/anchor must have unit world scale, no shear/reflection: {path}")
    return matrix


def _author(spec, exports, mapping=None, *, debug=False, extension=None):
    geometry = Usd.Stage.Open(str(exports / "geometry.usdc"))
    if not geometry:
        raise ValueError("Cannot open geometry.usdc")
    mapping = mapping if mapping is not None else semantic_object_map(geometry)
    if (
        UsdGeom.GetStageUpAxis(geometry) != "Z"
        or abs(UsdGeom.GetStageMetersPerUnit(geometry) - 1) > 1e-8
    ):
        raise ValueError("Geometry must be Z-up and meters")
    if geometry.GetPrimAtPath("/World/Physics"):
        raise ValueError("/World/Physics is reserved")
    if any(
        p.HasAPI(UsdPhysics.RigidBodyAPI)
        or p.HasAPI(UsdPhysics.CollisionAPI)
        or p.IsA(UsdPhysics.Joint)
        for p in geometry.Traverse()
    ):
        raise ValueError("Geometry already has physics; export clean geometry")
    # Anonymous layers prevent a failed authoring run from replacing the delivery.
    physics = Sdf.Layer.CreateAnonymous("physics.usda")
    root = Sdf.Layer.CreateAnonymous("scene.usda")
    root.subLayerPaths = [physics.identifier, str((exports / "geometry.usdc").resolve())]
    stage = Usd.Stage.Open(root)
    UsdGeom.SetStageUpAxis(stage, "Z")
    UsdGeom.SetStageMetersPerUnit(stage, 1)
    UsdPhysics.SetStageKilogramsPerUnit(stage, 1)
    world = stage.GetPrimAtPath("/World")
    if not world:
        raise ValueError("Geometry must have /World root")
    stage.SetDefaultPrim(world)
    stage.SetEditTarget(physics)
    scene = UsdPhysics.Scene.Define(stage, "/World/Physics/Scene")
    gravity = Gf.Vec3f(*spec.get("gravity", [0, 0, -9.81]))
    magnitude = gravity.GetLength()
    scene.CreateGravityMagnitudeAttr(magnitude)
    scene.CreateGravityDirectionAttr(gravity / magnitude if magnitude else Gf.Vec3f(0, 0, -1))

    def path_for(semantic_id):
        if semantic_id not in mapping or not stage.GetPrimAtPath(mapping[semantic_id]):
            raise ValueError(f"Missing semantic object: {semantic_id}")
        return Sdf.Path(mapping[semantic_id])

    materials = {}
    for name, values in spec["materials"].items():
        material = UsdShade.Material.Define(stage, "/World/Physics/Materials/" + name)
        api = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
        api.CreateStaticFrictionAttr(values["static_friction"])
        api.CreateDynamicFrictionAttr(values["dynamic_friction"])
        api.CreateRestitutionAttr(values["restitution"])
        if "restitution_combine_mode" in values:
            material.GetPrim().AddAppliedSchema("PhysxMaterialAPI")
            material.GetPrim().CreateAttribute(
                "physxMaterial:restitutionCombineMode", Sdf.ValueTypeNames.Token, custom=False
            ).Set(values["restitution_combine_mode"])
        materials[name] = material
    if spec["default_material"] not in materials:
        raise ValueError("Unknown default material")
    bodies, paths, colliders = {}, {}, set()
    collider_meshes = set()
    for body in spec["bodies"]:
        name = body["id"]
        path = path_for(body["object"])
        if name in bodies or path in paths.values():
            raise ValueError(f"Duplicate body ID or root: {name}")
        if any(path.HasPrefix(p) or p.HasPrefix(path) for p in paths.values()):
            raise ValueError(f"Nested body roots are unsupported: {path}")
        bodies[name], paths[name] = body, path
        prim = stage.GetPrimAtPath(path)
        if not prim.IsA(UsdGeom.Xformable):
            raise ValueError(f"Body root is not transformable: {path}")
        if body["type"] != "static":
            rigid_transform(stage, path)
            api = UsdPhysics.RigidBodyAPI.Apply(prim)
            api.CreateRigidBodyEnabledAttr(True)
            api.CreateKinematicEnabledAttr(body["type"] == "kinematic")
            UsdPhysics.MassAPI.Apply(prim).CreateMassAttr(body["mass_kg"])
        elif "mass_kg" in body:
            raise ValueError(f"Static body {name} must not specify mass")
        for collider in body["colliders"]:
            cp = path_for(collider["object"])
            if not cp.HasPrefix(path):
                raise ValueError(f"Collider {cp} is outside body {path}")
            if cp in colliders:
                raise ValueError(f"Duplicate collider: {cp}")
            colliders.add(cp)
            cprim = stage.GetPrimAtPath(cp)
            if not cprim.IsA(UsdGeom.Mesh):
                # Blender may export a mesh child under an object Xform.
                meshes = [p for p in Usd.PrimRange(cprim) if p.IsA(UsdGeom.Mesh)]
                if len(meshes) != 1:
                    raise ValueError(f"Collider must identify one mesh: {cp}")
                cprim = meshes[0]
            if cprim.GetPath() in collider_meshes:
                raise ValueError(f"Duplicate resolved collider mesh: {cprim.GetPath()}")
            collider_meshes.add(cprim.GetPath())
            if body["type"] != "static" and collider["approximation"] == "none":
                raise ValueError(f"Moving mesh collider requires a convex approximation: {cp}")
            targets = [cprim]
            approximation = collider["approximation"]
            if approximation == "coacd":
                from embodied_scene.usd.collision import generate
                targets = generate(stage, cprim, path, collider)
                approximation = "convexHull"
            material_name = collider.get("material", body.get("material", spec["default_material"]))
            if material_name not in materials:
                raise ValueError(f"Unknown physics material: {material_name}")
            for target in targets:
                UsdPhysics.CollisionAPI.Apply(target).CreateCollisionEnabledAttr(True)
                UsdPhysics.MeshCollisionAPI.Apply(target).CreateApproximationAttr(approximation)
                UsdShade.MaterialBindingAPI.Apply(target).Bind(
                    materials[material_name], materialPurpose="physics"
                )
                if "contact_offset_m" in collider or "rest_offset_m" in collider:
                    contact = collider.get("contact_offset_m")
                    rest = collider.get("rest_offset_m", 0)
                    if contact is None or contact <= rest:
                        raise ValueError("Explicit contact_offset_m must exceed rest_offset_m")
                    target.AddAppliedSchema("PhysxCollisionAPI")
                    for attr, value in (("contactOffset", contact), ("restOffset", rest)):
                        target.CreateAttribute(
                            "physxCollision:" + attr, Sdf.ValueTypeNames.Float, custom=False
                        ).Set(value)
            if collider.get("hide_visual", False):
                from embodied_scene.usd.collision import configure_proxy
                configure_proxy(cprim)
    joint_ids = set()
    for data in spec["joints"]:
        if data["id"] in joint_ids:
            raise ValueError(f"Duplicate joint: {data['id']}")
        joint_ids.add(data["id"])
        body1 = data["body1"]
        body0 = data.get("body0")
        if body1 not in bodies or body0 is not None and body0 not in bodies:
            raise ValueError(f"Unknown joint body: {data['id']}")
        if bodies[body1]["type"] != "dynamic" or body0 == body1:
            raise ValueError("Joint body1 must be dynamic and distinct from body0")
        anchor = rigid_transform(stage, path_for(data["anchor"]))
        kind = {
            "fixed": UsdPhysics.FixedJoint,
            "revolute": UsdPhysics.RevoluteJoint,
            "prismatic": UsdPhysics.PrismaticJoint,
        }[data["type"]]
        joint = kind.Define(stage, "/World/Physics/Joints/" + data["id"])
        for index, name in enumerate([body0, body1]):
            # Static bodies are attached to world with the world-space joint frame.
            dynamic = name is not None and bodies[name]["type"] != "static"
            transform = rigid_transform(stage, paths[name]) if dynamic else Gf.Matrix4d(1)
            local = anchor * transform.GetInverse()
            if dynamic:
                getattr(joint, f"CreateBody{index}Rel")().SetTargets([paths[name]])
            getattr(joint, f"CreateLocalPos{index}Attr")(Gf.Vec3f(local.ExtractTranslation()))
            getattr(joint, f"CreateLocalRot{index}Attr")(Gf.Quatf(local.ExtractRotationQuat()))
        joint.CreateCollisionEnabledAttr(data.get("collision_enabled", True))
        if data["type"] == "fixed":
            if "drive" in data or "limits" in data or "axis" in data:
                raise ValueError("Fixed joint cannot have drive, limits or axis")
            continue
        low, high = data["limits"]
        if low > 0 or high < 0 or low >= high:
            raise ValueError("Limits must be increasing and contain initial coordinate zero")
        joint.CreateAxisAttr(data["axis"])
        joint.CreateLowerLimitAttr(low)
        joint.CreateUpperLimitAttr(high)
        if "drive" in data:
            values = data["drive"]
            if not low <= values.get("target_position", 0) <= high:
                raise ValueError("Drive target is outside joint limits")
            drive = UsdPhysics.DriveAPI.Apply(
                joint.GetPrim(), "angular" if data["type"] == "revolute" else "linear"
            )
            drive.CreateTypeAttr("force")
            drive.CreateStiffnessAttr(values["stiffness"])
            drive.CreateDampingAttr(values["damping"])
            drive.CreateMaxForceAttr(values["max_force"])
            drive.CreateTargetPositionAttr(values.get("target_position", 0))
            drive.CreateTargetVelocityAttr(values.get("target_velocity", 0))
    ignored = [path_for(s) for s in spec.get("visual_only", [])]
    if any(p.HasPrefix(b) or b.HasPrefix(p) for p in ignored for b in paths.values()):
        raise ValueError("visual_only roots must not overlap physics bodies")
    covered = list(paths.values()) + ignored
    if extension is not None:
        from embodied_scene.integrations.isaacsim.config import ownership_paths
        covered += ownership_paths(extension, stage, mapping, occupied=covered)
    unclassified = [
        str(p.GetPath())
        for p in stage.Traverse()
        if p.IsA(UsdGeom.Mesh) and not any(p.GetPath().HasPrefix(root) for root in covered)
    ]
    if unclassified:
        raise ValueError("Unclassified meshes: " + ", ".join(unclassified))
    if extension is not None:
        from embodied_scene.integrations.isaacsim.authoring import author
        author(stage, extension, mapping)
    if debug:
        physics.Export(str(exports / "physics.usda"))
        delivery = Sdf.Layer.CreateAnonymous("delivery.usda")
        delivery.TransferContent(root)
        delivery.subLayerPaths = ["physics.usda", "geometry.usdc"]
        delivery.Export(str(exports / "scene.usda"))
    return stage


def validate_usd(scene_path: Path):
    stage = Usd.Stage.Open(str(scene_path))
    errors = []
    if not stage:
        raise ValueError(f"Cannot open {scene_path}")
    _, _, unresolved = UsdUtils.ComputeAllDependencies(str(scene_path))
    if unresolved:
        errors.append(f"Unresolved resources: {list(unresolved)}")
    if UsdGeom.GetStageUpAxis(stage) != "Z" or UsdGeom.GetStageMetersPerUnit(stage) != 1:
        errors.append("Invalid stage units")
    counts = {"bodies": 0, "colliders": 0, "joints": 0, "meshes": 0, "lights": 0}
    decompositions = {}
    if not stage.GetDefaultPrim():
        errors.append("Missing default prim")
    for prim in stage.Traverse():
        if prim.GetAttribute("collision:coacd"):
            from embodied_scene.usd.collision import validate_generated
            try:
                decompositions[str(prim.GetPath())] = validate_generated(stage, prim)
            except (ValueError, RuntimeError) as error:
                errors.append(str(error))
        if prim.GetTypeName() == "ParticleField3DGaussianSplat":
            from embodied_scene.assembly import validate_splats

            errors.extend(validate_splats(prim))
            counts["gaussian_fields"] = counts.get("gaussian_fields", 0) + 1
        if prim.HasAPI(UsdLux.LightAPI):
            counts["lights"] += 1
            light = UsdLux.LightAPI(prim)
            if not math.isfinite(light.GetIntensityAttr().Get()):
                errors.append(f"Invalid light intensity: {prim.GetPath()}")
        if prim.IsA(UsdGeom.Mesh):
            counts["meshes"] += 1
            mesh = UsdGeom.Mesh(prim)
            points = mesh.GetPointsAttr().Get() or []
            indices = mesh.GetFaceVertexIndicesAttr().Get() or []
            faces = mesh.GetFaceVertexCountsAttr().Get() or []
            if (
                not points
                or not faces
                or sum(faces) != len(indices)
                or any(n < 3 for n in faces)
                or any(i < 0 or i >= len(points) for i in indices)
                or any(not math.isfinite(v) for p in points for v in p)
            ):
                errors.append(f"Invalid mesh topology or points: {prim.GetPath()}")
            parent = prim.GetParent()
            while parent and not parent.IsPseudoRoot():
                if parent.IsA(UsdGeom.Gprim):
                    errors.append(f"Mesh beneath geometry leaf: {prim.GetPath()}")
                parent = parent.GetParent()
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            counts["bodies"] += 1
            mass = UsdPhysics.MassAPI(prim).GetMassAttr().Get()
            if mass is None or not math.isfinite(mass) or mass <= 0:
                errors.append(f"Invalid mass: {prim.GetPath()}")
            parent = prim.GetParent()
            while parent and not parent.IsPseudoRoot():
                if parent.HasAPI(UsdPhysics.RigidBodyAPI):
                    errors.append(f"Nested rigid body: {prim.GetPath()}")
                parent = parent.GetParent()
        if prim.HasAPI(UsdPhysics.CollisionAPI):
            counts["colliders"] += 1
            if prim.IsA(UsdGeom.Mesh) and UsdGeom.Imageable(prim).ComputePurpose() == "guide":
                if UsdGeom.Imageable(prim).ComputeVisibility() != "inherited":
                    errors.append(f"Guide collider has hidden ancestry: {prim.GetPath()}")
                for purpose in ("", "preview", "full"):
                    if UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial(purpose)[0]:
                        errors.append(f"Guide collider has visual material: {prim.GetPath()}")
            mat, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial("physics")
            from embodied_scene.integrations.isaacsim.schema import has_api
            soft_material = mat and has_api(mat.GetPrim(), "OmniPhysicsDeformableMaterialAPI")
            if not mat or not (mat.GetPrim().HasAPI(UsdPhysics.MaterialAPI) or soft_material):
                errors.append(f"Missing physics material: {prim.GetPath()}")
        if prim.IsA(UsdPhysics.Joint):
            counts["joints"] += 1
            joint = UsdPhysics.Joint(prim)
            frames = []
            valid_frames = True
            for rel in [joint.GetBody0Rel(), joint.GetBody1Rel()]:
                if len(rel.GetTargets()) > 1:
                    errors.append(f"Multiple joint targets: {prim.GetPath()}")
                for target in rel.GetTargets():
                    body = stage.GetPrimAtPath(target)
                    if not body or not body.HasAPI(UsdPhysics.RigidBodyAPI):
                        errors.append(f"Invalid joint target: {target}")
                        valid_frames = False
            if not joint.GetBody1Rel().GetTargets():
                errors.append(f"Missing body1 target: {prim.GetPath()}")
            if valid_frames:
                for i in range(2):
                    targets = getattr(joint, f"GetBody{i}Rel")().GetTargets()
                    matrix = Gf.Matrix4d(1)
                    matrix.SetRotate(Gf.Quatd(getattr(joint, f"GetLocalRot{i}Attr")().Get()))
                    matrix.SetTranslateOnly(Gf.Vec3d(getattr(joint, f"GetLocalPos{i}Attr")().Get()))
                    if targets:
                        matrix *= UsdGeom.XformCache().GetLocalToWorldTransform(
                            stage.GetPrimAtPath(targets[0])
                        )
                    frames.append(matrix)
                if (
                    max(abs(frames[0][i][j] - frames[1][i][j]) for i in range(4) for j in range(4))
                    > 1e-4
                ):
                    errors.append(f"Initial joint frames disagree: {prim.GetPath()}")
            if prim.IsA(UsdPhysics.RevoluteJoint) or prim.IsA(UsdPhysics.PrismaticJoint):
                low = prim.GetAttribute("physics:lowerLimit").Get()
                high = prim.GetAttribute("physics:upperLimit").Get()
                if (
                    not math.isfinite(low)
                    or not math.isfinite(high)
                    or not low <= 0 <= high
                    or low >= high
                ):
                    errors.append(f"Invalid limits: {prim.GetPath()}")
    return {
        "status": "fail" if errors else "pass",
        "errors": errors,
        "counts": counts,
        "collision_generation": decompositions,
        "dynamic_validation": {"status": "pending_user", "simulator": "Isaac Sim"},
        "limitations": [
            (
                "Static checks do not certify contacts, clearance, inertia, "
                "material appearance or actual joint motion."
            )
        ],
    }


def author_stage(spec_path: Path, exports: Path, mapping=None, *, debug=False):
    spec = validate_specification(spec_path, "physics.schema.json")

    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Physics values must be finite")
        if isinstance(value, dict):
            for item in value.values():
                finite(item)
        if isinstance(value, list):
            for item in value:
                finite(item)

    finite(spec)
    from embodied_scene.integrations.isaacsim.config import load_extension
    return _author(spec, exports, mapping, debug=debug, extension=load_extension(spec_path))


def author_physics(spec_path: Path, exports: Path):
    """Low-level helper for existing geometry; no sidecar reports or hashes."""
    try:
        from embodied_scene.integrations.isaacsim.config import load_extension
        if load_extension(spec_path) is not None:
            raise ValueError("Isaac Sim extensions require the shared export_scene.py pipeline")
        stage = author_stage(spec_path, exports)
        stage.Flatten().Export(str(exports / "scene.usdc"))
        return validate_usd(exports / "scene.usdc")
    except (ValueError, OSError, KeyError, jsonschema.ValidationError, Tf.ErrorException) as error:
        return {
            "status": "fail",
            "errors": [str(error)],
            "dynamic_validation": {"status": "pending_user", "simulator": "Isaac Sim"},
        }
