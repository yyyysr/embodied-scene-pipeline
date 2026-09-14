# Agent workflow

## Build loop

1. Parse input evidence into `task.yaml` and a semantic `scene.yaml` draft.
2. Assign stable identifiers and record uncertain floorplan assumptions.
3. For tabletop references, resolve the optional background decision described
   in `docs/background-generation.md`; do not call image or 3DGS providers when
   the background is blank, task-only, unspecified, or cheaply built in Blender.
4. When 3DGS is selected, prepare and visually accept a clean plate before world
   generation. Preserve the original reference and keep task entities explicit.
5. Ask Structure Agent to author and review the complete global shell.
6. Export `build/structure_contract.json` from resolved rooms, shared walls, and openings.
7. Ask Room Agents for details only after the structure contract is available.
8. Ask Asset Agents only for difficult assets with explicit spatial boundaries.
9. Integrate source scripts through the declared Blender entry point in a clean scene.
10. Add a removable diagnostic rig in `__REVIEW__`.
11. Validate and render overview, top, and task views.
12. Review evidence and prioritize blocking, major, and cosmetic defects.
13. Synchronize accepted discoveries into specifications or source and rebuild.

## Escalate to MCP when

- a defect is view-dependent and diagnostic renders cannot isolate it;
- collection, modifier, material, or dependency state needs live inspection;
- a small experiment is faster interactively.

Do not leave an accepted fix only inside an interactive Blender session.
