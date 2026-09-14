---
name: export-scene
description: Export a modeled Blender scene as one USD delivery with pxr physics and static validation. Use after modeling or when rebuilding an existing scene's USD output.
---

# Export scene

Read `docs/usd-physics.md` and the workspace scene/task/physics specifications.

Check source readiness: stable semantic IDs, complete body membership, useful joint
frames, cavity-preserving collisions, and actual lights outside __REVIEW__. Repair
source or configuration if missing; do not invent a parallel JSON scene description.

Use the shared entry point:

```bash
.venv/bin/python scripts/export_scene.py workspaces/<id>
```

The full `scripts/run_blender.py` pipeline already invokes this phase. Use --blend
and --physics only for an existing prepared source. Do not write per-case exporters.

Deliver exports/scene.usdc and referenced textures. Query this final USD to debug.
Keep one review/report.json. Use --debug only for a concrete investigation; do not
add hashes, manifests, permanent intermediate layers or duplicate reports.

Static success is not Isaac Sim success. State pending visual/dynamic checks and
repair accepted issues in source/configuration before rebuilding.
