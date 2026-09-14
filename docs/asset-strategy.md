# Asset strategy

Choose the least expensive method that satisfies task and visual requirements.

| Asset type | Preferred path |
| --- | --- |
| Walls, floors, doors, windows, work surfaces | Agent-authored Blender geometry |
| Cabinets, shelves, sinks, simple furniture | Agent-authored Blender geometry |
| Complex upholstered, organic, or highly curved assets | 3D-generation provider, then agent normalization |
| Non-interactive distant visual context | Optional World Labs/3DGS |
| Manipulable or collision-critical object | Explicit mesh, never 3DGS alone |

Provider results are untrusted inputs until scale, axes, origin, materials, geometry, and licensing metadata are checked.

For FAL Hunyuan3D text generation, optional generative reference preparation,
regeneration rules, and the acceptance boundary, see `docs/generated-assets.md`.

For optional tabletop 3DGS backgrounds, apply the evidence and clean-plate gate
in `docs/background-generation.md` before any provider call. A generated world
collider is reference geometry and never replaces explicit task geometry.
