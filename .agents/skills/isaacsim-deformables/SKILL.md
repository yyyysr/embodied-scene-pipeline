---
name: isaacsim-deformables
description: Author Isaac Sim soft-body and cloth USD assets from source geometry, physical materials, mesh-generation settings and bind poses using the offline scene pipeline.
---

# Isaac Sim deformables

Read `docs/isaacsim-deformables/README.md` and `compatibility.md` in that directory
to choose the target schema profile. Configure `specs/isaacsim.yaml`, referenced
by `physics.yaml`.

Use `asset-contract.md` to resolve volume versus surface, physical scale,
source/rest shape, ownership, mass and bind poses. Volume assets contain a closed
source mesh and automatic tetrahedral-generation declarations; the platform
generates the required mesh data before simulation. Surface assets contain an
explicit triangle simulation mesh with known nodes for attachments.

For interacting rigid assets, follow `docs/collision-proxies.md`: primitives for
simple shapes, offline CoACD for ordinary concave geometry. GPU cooking compatibility
is distinct from geometric quality of the generated convex parts.
Dedicated rigid collision proxies use guide purpose and physics-only bindings;
source/render meshes retain their visual purpose and materials.

Read `materials-and-contact.md` to distinguish appearance, mechanical properties,
contact settings and solver parameters. Record parameter provenance and check
mass against physical dimensions and density.

Model with workspace Blender Python and registered references. Use the shared
build/export commands to write typed USD declarations and reopen the final
candidate for the checks in `validation.md`. Deliver `exports/scene.usdc` and
referenced textures; summarize evidence in `review/report.json`.
