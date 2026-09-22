"""Offline authoring of volume generation recipes and explicit surface meshes."""

from pxr import Usd, UsdShade

from . import attachments, materials, meshes
from .config import ownership_paths, validate_config
from .schema import apply, set_attr

SOLVER_ATTRIBUTES = {
    "position_iterations": "solverPositionIterationCount",
    "linear_damping_per_s": "linearDamping",
    "settling_damping_per_s": "settlingDamping",
    "settling_threshold_m_s": "settlingThreshold",
    "sleep_threshold_m_s": "sleepThreshold",
    "max_depenetration_velocity_m_s": "maxDepenetrationVelocity",
    "max_linear_velocity_m_s": "maxLinearVelocity",
    "collision_pair_update_frequency": "collisionPairUpdateFrequency",
    "collision_iteration_multiplier": "collisionIterationMultiplier",
}


def body_values(spec):
    values = {}
    if "mass_kg" in spec:
        values["omniphysics:mass"] = spec["mass_kg"]
    values["physxDeformableBody:selfCollision"] = spec["contact"].get("self_collision", False)
    values["physxDeformableBody:enableSpeculativeCCD"] = spec["contact"].get(
        "speculative_ccd", False
    )
    distance = spec["contact"].get("self_collision_filter_distance_m", "auto")
    if distance != "auto":
        values["physxDeformableBody:selfCollisionFilterDistance"] = distance
    for key, value in spec.get("solver", {}).items():
        if value == "auto":
            value = 0 if key == "collision_pair_update_frequency" else -1.0
        values["physxDeformableBody:" + SOLVER_ATTRIBUTES[key]] = value
    return values


def author(stage, config, mapping):
    validate_config(config)
    ownership_paths(config, stage, mapping)
    scene = stage.GetPrimAtPath("/World/Physics/Scene")
    if not scene:
        raise ValueError("Missing shared Physics Scene")
    apply(scene, "PhysxSceneAPI")
    set_attr(scene, "physxScene:enableGPUDynamics", True)
    set_attr(scene, "physxScene:broadphaseType", "GPU")
    set_attr(
        scene,
        "physxScene:timeStepsPerSecond",
        config.get("scene", {}).get("time_steps_per_second", 120),
    )
    mats = {name: materials.author(stage, name, spec) for name, spec in config["materials"].items()}
    bodies = {}
    for spec in config["deformables"]:
        root, sim = meshes.author(stage, spec, mapping)
        apply(root, "PhysxBaseDeformableBodyAPI")
        if spec["kind"] == "surface":
            apply(root, "PhysxSurfaceDeformableBodyAPI")
        root.CreateRelationship("omniphysics:simulationOwner", custom=False).SetTargets(
            [scene.GetPath()]
        )
        for name, value in body_values(spec).items():
            set_attr(root, name, value)
        UsdShade.MaterialBindingAPI.Apply(root).Bind(
            mats[spec["material"]], materialPurpose="physics"
        )
        from pxr import UsdPhysics

        for prim in Usd.PrimRange(root):
            if prim.HasAPI(UsdPhysics.CollisionAPI):
                apply(prim, "PhysxCollisionAPI")
                set_attr(prim, "physxCollision:restOffset", spec["contact"]["rest_offset_m"])
                set_attr(prim, "physxCollision:contactOffset", spec["contact"]["contact_offset_m"])
        bodies[spec["id"]] = (root, sim)
    attachments.author(stage, config, bodies, mapping)
