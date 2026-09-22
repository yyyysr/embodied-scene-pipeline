"""Explicit USD types for the supported Omni Physics/PhysX declaration subset."""

from pxr import Sdf


def apply(prim, schema):
    prim.AddAppliedSchema(schema)


def has_api(prim, schema):
    opinion = prim.GetMetadata("apiSchemas")
    return bool(opinion and schema in opinion.GetAppliedItems())


TYPES = {
    "deformablePose:default:omniphysics:purposes": Sdf.ValueTypeNames.TokenArray,
    "deformablePose:default:omniphysics:points": Sdf.ValueTypeNames.Point3fArray,
    "omniphysics:restShapePoints": Sdf.ValueTypeNames.Point3fArray,
    "omniphysics:restTriVtxIndices": Sdf.ValueTypeNames.Int3Array,
    "omniphysics:restBendAnglesDefault": Sdf.ValueTypeNames.Token,
    "omniphysics:vtxIndicesSrc0": Sdf.ValueTypeNames.IntArray,
    "omniphysics:localPositionsSrc1": Sdf.ValueTypeNames.Point3fArray,
    "physxScene:broadphaseType": Sdf.ValueTypeNames.Token,
}
for name in (
    "omniphysics:mass",
    "omniphysics:youngsModulus",
    "omniphysics:poissonsRatio",
    "omniphysics:dynamicFriction",
    "omniphysics:density",
    "omniphysics:surfaceThickness",
    "omniphysics:surfaceBendStiffness",
    "physxDeformableMaterial:elasticityDamping",
    "physxDeformableMaterial:bendDamping",
    "physxCollision:restOffset",
    "physxCollision:contactOffset",
):
    TYPES[name] = Sdf.ValueTypeNames.Float
for name in (
    "selfCollisionFilterDistance",
    "linearDamping",
    "settlingDamping",
    "settlingThreshold",
    "sleepThreshold",
    "maxDepenetrationVelocity",
    "maxLinearVelocity",
):
    TYPES["physxDeformableBody:" + name] = Sdf.ValueTypeNames.Float
for name in (
    "resolution",
    "solverPositionIterationCount",
    "collisionPairUpdateFrequency",
    "collisionIterationMultiplier",
):
    TYPES["physxDeformableBody:" + name] = Sdf.ValueTypeNames.UInt
for name in ("selfCollision", "enableSpeculativeCCD", "autoDeformableBodyEnabled"):
    TYPES["physxDeformableBody:" + name] = Sdf.ValueTypeNames.Bool
TYPES["physxScene:enableGPUDynamics"] = Sdf.ValueTypeNames.Bool
TYPES["physxScene:timeStepsPerSecond"] = Sdf.ValueTypeNames.UInt


def set_attr(prim, name, value):
    attr = prim.CreateAttribute(name, TYPES[name], custom=False)
    if not attr.Set(value):
        raise ValueError(f"Cannot author {prim.GetPath()}.{name}")
