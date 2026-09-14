---
name: create-scene
description: Create or rebuild an embodied-AI Blender scene from a task description, scene description, YAML specifications, and optional reference images. Use when Codex needs to initialize a scene workspace, convert intent into scene specifications, delegate structure/room/asset work, generate Blender Python, or integrate scene components.
---

# Create scene

1. Read the root `AGENTS.md`, `docs/project-context.md`, and `docs/scene-specification.md`.
2. Preserve the original prompt and reference images under the workspace `input/` directory.
3. Create and validate `specs/task.yaml` and `specs/scene.yaml` before generating geometry.
4. For a tabletop reference, read `docs/background-generation.md` and resolve
   the background decision before calling any paid provider. Skip 3DGS when the
   background is blank, task-only, unspecified, or cheaply built in Blender.
   When useful static context is contaminated, use the image-generation skill
   or configured FAL editor to create `clean_plate.png`, visually accept it, and
   only then call the World Labs helper. Never overwrite the original reference.
5. Assign stable semantic identifiers to rooms, surfaces, objects, and task entities.
6. Select modeling paths using `docs/asset-strategy.md`. When one complex asset
   is routed to FAL Hunyuan3D, read `docs/generated-assets.md` and choose direct
   text-to-3D, a text-generated single-object reference, or generative editing
   of a source image. Do not add a segmentation pipeline. Visually accept any
   generated `reference.png` before the image-to-3D call, and treat `asset.glb`
   as unreviewed until it is normalized and validated in Blender.
7. For a multi-room architectural interior, read
   [references/interior-modeling.md](references/interior-modeling.md) before
   authoring the structure, openings, or articulated casework.
8. Delegate only when the component boundary and output contract are explicit.
9. Generate Blender Python under the workspace `source/` directory.
10. Build from a clean scene and save generated results under `build/`.
11. Invoke the `review-scene` skill before accepting the result.

Keep diagnostic cameras and lights separate from final scene lighting. Never make generated `.blend` state the only copy of an accepted modeling decision.
