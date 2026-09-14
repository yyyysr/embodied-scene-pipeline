---
name: create-scene
description: Create or rebuild an embodied-AI Blender scene from a task description, scene description, YAML specifications, and optional reference images. Use when Codex needs to initialize a scene workspace, convert intent into scene specifications, delegate structure/room/asset work, generate Blender Python, or integrate scene components.
---

# Create scene

1. Read the root `AGENTS.md`, `docs/project-context.md`, and `docs/scene-specification.md`.
2. Preserve the original prompt and reference images under the workspace `input/` directory.
3. Create and validate `specs/task.yaml` and `specs/scene.yaml` before generating geometry.
4. Assign stable semantic identifiers to rooms, surfaces, objects, and task entities.
5. Select modeling paths using `docs/asset-strategy.md`.
6. For a multi-room architectural interior, read
   [references/interior-modeling.md](references/interior-modeling.md) before
   authoring the structure, openings, or articulated casework.
7. Delegate only when the component boundary and output contract are explicit.
8. Generate Blender Python under the workspace `source/` directory.
9. Build from a clean scene and save generated results under `build/`.
10. Invoke the `review-scene` skill before accepting the result.

Keep diagnostic cameras and lights separate from final scene lighting. Never make generated `.blend` state the only copy of an accepted modeling decision.
