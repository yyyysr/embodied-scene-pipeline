# Blender conventions

- Units: meters; scale length 1.0.
- Coordinates: right-handed, Z up.
- Collections: `STRUCTURE`, `ROOMS`, `ASSETS`, `TASK`, and `__REVIEW__`.
- Names: `<kind>__<semantic_id>`.
- Origins: floor-standing objects at footprint center on the floor; manipulable objects at a useful physical pivot.
- Apply scale before export unless a downstream contract says otherwise.
- Diagnostic cameras and lights belong only to `__REVIEW__` and must be removable without changing the scene.
- Rebuild from a clean file; do not depend on hidden manual state.


## USD physics preparation

Read `docs/usd-physics.md` before creating movable assemblies. Register stable
semantic IDs for body roots, collider objects and joint anchor Empties. Parent
visual/collision members explicitly; `context.register` only assigns metadata.
Keep moving roots and joint frames free of world scale, shear and reflection.
Describe physics in `specs/physics.yaml`, independently of scene appearance.
