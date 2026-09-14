# Repository instructions

## Goal

Build reproducible Blender scenes for embodied-AI tasks from text and optional reference images. Optimize for task usability, spatial consistency, editable source, and visual review rather than a single attractive render.

## Current phase

- Use the native agent entry point.
- Keep task semantics separate from scene appearance.
- Use Blender Python as the primary modeling interface.
- Treat Blender MCP as optional escalation for live inspection.
- Export geometry with Blender’s native USD exporter; author physics downstream with pxr.
- Read `docs/usd-physics.md` for the physics contract. Isaac Sim dynamic validation is performed by the user; never report it as passed from static checks.

## Required workflow

1. Read `docs/project-context.md` and the applicable YAML specifications.
2. Preserve original user input under `workspaces/<id>/input/`.
3. For tabletop references, apply `docs/background-generation.md` before any
   image-editing or 3DGS provider call; skip optional generation when static
   visual context is absent or unnecessary.
4. Update specifications before implementation when intent changes. For an
   image-derived irregular floorplan, begin with a semantic draft instead of
   inventing exact polygons; the Structure Agent resolves geometry and exports
   `build/structure_contract.json` before dependent room work begins.
5. Build the scene from source-controlled Python.
6. Add diagnostic cameras and lights in a dedicated review collection.
7. validate geometry, naming, visibility, scale, and task clearances.
8. Render overview, top, and task views.
9. Write a machine-readable review report.
10. Repair specifications or source scripts, then rebuild.

## Agent ownership

- The root agent is Scene Director and owns global composition and integration.
- Structure Agent owns the complete spatial shell, including irregular floor polygons, walls, floors, ceilings, doors, and windows.
- Structure Agent registers resolved rooms, shared walls, and openings through
  the build context. Room Agent work begins only after that contract exists.
- Room Agent owns one assigned room and must respect the structure contract.
- Asset Agent owns one complex asset or coherent asset set.
- Review Agent is read-only with respect to generated `.blend` files; it reports issues and proposes source changes.
- Never let multiple agents edit the same `.blend` file concurrently. Exchange scripts, YAML manifests, meshes, renders, and reports.

## Modeling policy

- Model walls, floors, doors, windows, tabletops, and room layout in Blender; they are not fixed procedural templates.
- Prefer agent-authored Blender geometry for regular, editable objects.
- Use the declared workspace Blender entry point for complex scenes. YAML is a
  semantic contract, not a replacement geometry language; the runtime may not
  restrict authored geometry to its primitive convenience builder.
- Use a 3D-generation provider for assets whose curved or organic geometry would otherwise be low quality.
- Use 3DGS only for non-interactive visual context. Never represent collision-critical or manipulable geometry solely as 3DGS.
- Store dimensions in meters and use Z-up coordinates.

## Change discipline

- Never place secrets in source files.
- Never make an MCP-only correction. Reproduce every accepted change in YAML or Python.
- Do not commit generated workspaces, `.blend` files, renders, caches, or provider downloads.
- Run relevant tests and schema validation after changes.

## Delivery and output discipline

- The default build continues through native USD export and pxr physics authoring.
  Geometry-only work is an explicit exception. Read docs/usd-physics.md.
- Deliver exports/scene.usdc and its referenced textures only. Keep semantic names,
  parent hierarchy and formal lighting. Prepare physics semantics during modeling.
- Keep one review/report.json; no default hashes, manifests, duplicate JSON scene
  data, backup exports or review iteration archives. Inspect the final USD directly.
- Intermediates belong in memory or temporary directories. Retain debug files only
  for a concrete investigation; create optional directories on demand.
