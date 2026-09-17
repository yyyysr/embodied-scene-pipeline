# Agent workflow

## Build loop

1. Parse input evidence into `task.yaml` and a semantic `scene.yaml` draft.
2. Assign stable identifiers and record uncertain floorplan assumptions. Resolve
   per-part material intent and formal lighting for the intended renderer using
   the appearance guidance in `docs/scene-specification.md`.
3. For tabletop references, resolve the optional background decision described
   in `docs/background-generation.md`; do not call image or 3DGS providers when
   the background is blank, task-only, unspecified, or cheaply built in Blender.
4. When 3DGS is selected, prepare and visually accept a clean plate before world
   generation. Preserve the original reference and keep task entities explicit.
5. Ask Structure Agent to author and review the complete global shell.
6. Export `build/structure_contract.json` from resolved rooms, shared walls, and openings.
7. Ask Room Agents for details only after the structure contract is available.
8. Ask Asset Agents only for difficult assets with explicit spatial boundaries.
9. Normalize generated geometry/materials, implement the resolved formal lighting,
   and integrate source scripts through the declared Blender entry point in a clean scene.
10. When explicit geometry and a 3DGS background both exist, align them through
    the scene assembly workflow in `docs/scene-editor.md`. Treat explicit geometry
    as the meter/Z-up authority, save the accepted transform in `scene.yaml`, and
    never treat the identity default as evidence of alignment.
11. Add a removable diagnostic rig in `__REVIEW__`.
12. Validate and render overview, top, and task views.
13. Review evidence and prioritize blocking, major, and cosmetic defects.
14. Synchronize accepted discoveries into specifications or source and rebuild.
15. Export native USD, map resolved appearance settings and author physics through
    the shared delivery pipeline. Compare the final USD with the specifications
    using `docs/usd-physics.md`; record static conformance separately from the
    user's target-renderer and dynamic acceptance.

## Escalate to MCP when

- a defect is view-dependent and diagnostic renders cannot isolate it;
- collection, modifier, material, or dependency state needs live inspection;
- a small experiment is faster interactively.

Do not leave an accepted fix only inside an interactive Blender session.
