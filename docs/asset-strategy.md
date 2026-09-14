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

