---
name: export-scene
description: Export a modeled Blender scene as one USD delivery with pxr physics and static validation. Use after modeling or when rebuilding an existing scene's USD output.
---

# Export scene

Read `docs/usd-physics.md` and the workspace scene/task/physics and lighting
specifications. Resolve material and lighting intent before export using the
material normalization guidance in `docs/generated-assets.md` and the defaults
in [../create-scene/references/lighting.md](../create-scene/references/lighting.md).

Check source readiness: stable semantic IDs, complete body membership, useful joint
frames, cavity-preserving collisions, and actual lights outside __REVIEW__. Repair
source or configuration if missing; do not invent a parallel JSON scene description.
Opening an asset must already reveal its intended functional interior in Blender;
adding a joint downstream cannot repair a solid or incorrectly modeled body.
Map the resolved surface materials and target-renderer light settings into USD.
Use Blender's native exporter for supported data and reproducible source-backed
adaptation through the shared delivery pipeline where mapping is needed. Blender
preview light power and file-format material fallbacks do not define delivery intent.

Use the shared entry point:

```bash
.venv/bin/python scripts/export_scene.py workspaces/<id>
```

The full `scripts/run_blender.py` pipeline already invokes this phase. Use --blend
and --physics only for an existing prepared source. Do not write per-case exporters.

Reopen the final USD and compare bound shaders, texture channels/color spaces,
and effective environment/local light attributes against the resolved specifications.
For an untextured environment, verify the effective texture asset is unset/empty
and package only remaining referenced textures. See the appearance acceptance
criteria in `docs/usd-physics.md`; correct source/specification mismatches before delivery.

Deliver exports/scene.usdc and referenced textures. Query this final USD to debug.
Keep one review/report.json. Use --debug only for a concrete investigation; do not
add hashes, manifests, permanent intermediate layers or duplicate reports.

Static success is not Isaac Sim success. State pending visual/dynamic checks and
repair accepted issues in source/configuration before rebuilding.
