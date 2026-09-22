# Target profiles and NVIDIA references

Interacting rigid geometry follows [collision proxies](../collision-proxies.md).
Explicit convex parts still require GPU-compatible cooking. NVIDIA's
[collider reference](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/110.1/dev_guide/rigid_bodies_articulations/rigid_bodies.html#rigid-body-collider-compatibility)
identifies CPU-only multi-material triangle meshes and elongated convex cooking
limitations. Offline convexity checks do not certify GPU cooking or dynamic contact.

Reviewed 2026-09-22. `isaacsim_6_0` and `isaacsim_6_1` select the supported
Omni Physics/PhysX vocabulary for those target families. The builder uses ordinary
`usd-core` with explicit API tokens, property types and relationships.

OpenUSD preserves applied API tokens even without their plugins. The writer uses
`AddAppliedSchema`, typed `CreateAttribute(..., custom=False)` and relationships.
Checks inspect composed `apiSchemas` metadata and property types; registered-schema
reflection alone does not expose unregistered target APIs.

## Sources

- [Deformable bodies](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/110.1/dev_guide/deformables/deformable_bodies.html):
  automatic volume hierarchy, bind poses, binding and implementation limits.
- [PhysX schema](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/110.1/dev_guide/deformables/physx_deformable_schema.html):
  mesh generation, resolution, solver settings and parameter bounds.
- [Omni Physics schema](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/110.1/dev_guide/deformables/omniphysics_deformable_schema.html):
  body, material, state and poses.
- [Migration guide](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/110.1/dev_guide/deformables/deformable_migration.html):
  transition from legacy deformables and particle cloth.
- [Helper API](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/110.1/extensions/runtime/source/omni.physx/docs/api/python.html):
  reference authoring patterns.

The inspected 6.1 helper source uses the supported `OmniPhysics...` tokens and
`omniphysics:*` properties. On upgrade, compare schema types, defaults and helper
hierarchy construction; update authoring and round-trip tests together.

The exposed subset uses one material per body, dynamic friction, matched surface
rest/current topology and explicit surface attachments. Material subsets, independent
surface stretch/shear overrides and static friction are outside the supported subset.
