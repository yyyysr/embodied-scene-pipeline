# Agent workflow

## Build loop

1. Parse input evidence into `task.yaml` and a semantic `scene.yaml` draft.
2. Assign stable identifiers and record uncertain floorplan assumptions.
3. Ask Structure Agent to author and review the complete global shell.
4. Export `build/structure_contract.json` from resolved rooms, shared walls, and openings.
5. Ask Room Agents for details only after the structure contract is available.
6. Ask Asset Agents only for difficult assets with explicit spatial boundaries.
7. Integrate source scripts through the declared Blender entry point in a clean scene.
8. Add a removable diagnostic rig in `__REVIEW__`.
9. Validate and render overview, top, and task views.
10. Review evidence and prioritize blocking, major, and cosmetic defects.
11. Synchronize accepted discoveries into specifications or source and rebuild.

## Escalate to MCP when

- a defect is view-dependent and diagnostic renders cannot isolate it;
- collection, modifier, material, or dependency state needs live inspection;
- a small experiment is faster interactively.

Do not leave an accepted fix only inside an interactive Blender session.
