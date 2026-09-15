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
   Decide which assets must open or expose usable interiors before modeling their
   exterior. Include appliances as well as doors and cabinets; make appearance-only
   simplifications explicit in the scene specification.
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
11. Prepare `specs/physics.yaml` and physical assembly hierarchy during modeling,
    following `docs/usd-physics.md`. Give colliders and anchors stable semantic IDs;
    preserve cavities and distinguish installed fixtures from movable assets.
12. Invoke `review-scene` for geometry/visual review, then `export-scene` for final
    USD delivery. The shared run_blender.py command runs build and export together;
    use --geometry-only only when the user requests that boundary.

Keep diagnostic cameras and lights separate from final scene lighting. Never make generated `.blend` state the only copy of an accepted modeling decision.

For formal lighting, read [references/lighting.md](references/lighting.md) before
choosing initial light parameters. Set lighting for the intended renderer during
modeling, rather than postponing illumination decisions until USD export.

Author review entry points with explicit view/asset selection and a build-only
mode. A rebuild must not automatically regenerate every articulation image or
create an iteration directory. Follow review-scene for evidence reuse.

Create directories only when needed. Do not add hashes, duplicate JSON scene
representations or permanent intermediates. Default output is governed by
`docs/usd-physics.md`; keep formal scene lighting outside __REVIEW__.
