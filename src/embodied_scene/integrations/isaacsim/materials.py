"""USD deformable material authoring for the new Omni Physics schema."""

from pxr import UsdShade

from .schema import apply, set_attr


def expected_values(spec):
    values = {
        "omniphysics:youngsModulus": spec["youngs_modulus_pa"],
        "omniphysics:poissonsRatio": spec["poissons_ratio"],
        "omniphysics:dynamicFriction": spec["dynamic_friction"],
    }
    for key, attr in {
        "density_kg_m3": "omniphysics:density",
        "surface_thickness_m": "omniphysics:surfaceThickness",
        "elasticity_damping_per_s": "physxDeformableMaterial:elasticityDamping",
        "bend_damping_per_s": "physxDeformableMaterial:bendDamping",
    }.items():
        if key in spec:
            values[attr] = spec[key]
    if "bend_stiffness_pa" in spec:
        bend = spec["bend_stiffness_pa"]
        if bend == "isotropic_shell":
            bend = spec["youngs_modulus_pa"] / (12 * (1 - spec["poissons_ratio"] ** 2))
        values["omniphysics:surfaceBendStiffness"] = bend
    return values


def author(stage, name, spec):
    path = "/World/Physics/DeformableMaterials/" + name
    if stage.GetPrimAtPath(path):
        raise ValueError(f"Reserved material path already exists: {path}")
    material = UsdShade.Material.Define(stage, path)
    prim = material.GetPrim()
    apply(prim, "OmniPhysicsDeformableMaterialAPI")
    apply(prim, "PhysxDeformableMaterialAPI")
    if "surface_thickness_m" in spec:
        apply(prim, "OmniPhysicsSurfaceDeformableMaterialAPI")
        apply(prim, "PhysxSurfaceDeformableMaterialAPI")
    for attribute, value in expected_values(spec).items():
        set_attr(prim, attribute, value)
    return material
