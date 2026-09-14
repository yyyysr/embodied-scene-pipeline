# Architecture

## Layers

1. **Input evidence**: task description, scene description, and reference images.
2. **Structured intent**: versioned YAML specifications validated by JSON Schema.
3. **Modeling source**: Blender Python generated or edited by agents.
4. **Build products**: `.blend`, meshes, textures, and provider outputs.
5. **Review evidence**: diagnostic renders and machine-readable reports.
6. **Exports**: native Blender geometry and in-memory pxr physics combined into
   one scene.usdc plus referenced textures. Temporary interchange is cleaned up;
   final-file checks merge into review/report.json.
7. **User validation**: Isaac Sim visual and dynamic checks performed by the user.

## Key boundary

Host-side Python under `src/` must not import `bpy`. Blender-only modules live under `blender_runtime/` and execute with Blender's Python interpreter. This keeps schemas and workspace tools testable without Blender.

## Integration contract

Subagents produce isolated scripts, specifications, manifests, or asset files. The Scene Director integrates them in deterministic order: structure, rooms, assets, review rig, validation, render, export.

