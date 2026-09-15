---
name: review-scene
description: Validate and visually review a generated embodied-AI Blender scene. Use when Codex needs to add diagnostic cameras and lighting, render intermediate views, inspect a report, identify geometric or task-level defects, or plan source-level repairs.
---

# Review scene

1. Read the task and scene specifications before inspecting appearance.
2. Run deterministic validation and save `review/report.json`.
3. Establish overview, top, and task evidence using the removable `__REVIEW__`
   collection. On later iterations, render only views whose evidence is missing
   or invalidated by the changes; reuse inspected, unaffected evidence.
4. For a multi-room or articulated interior, read
   [references/interior-review.md](references/interior-review.md), render the
   missing or affected room and articulation evidence, and review it before accepting the
   global views.
5. Check, in order: missing required entities, invalid transforms, task clearances, spatial containment, scale, visibility, geometry defects, and visual quality.
6. Classify findings as blocking, major, or cosmetic and cite the affected semantic identifiers.
7. Propose changes to YAML or Blender Python, not opaque manual edits.
8. Rebuild from source after repairs. Update one review/report.json; retain separate
   iterations only when a concrete comparison needs them.
9. Inspect the final exports/scene.usdc directly for naming, hierarchy, physics and
   light attributes. Do not substitute JSON counts for final-file inspection, or
   claim visual illumination/simulation from static checks. See docs/usd-physics.md.

Escalate to Blender MCP only when reports and diagnostic renders cannot isolate the issue. Synchronize every accepted MCP edit back to source.

Before rendering, identify the question each image must answer and select the
affected assets/views. First acceptance usually needs closed and open views;
additional poses or angles need a concrete reason. Batch related source repairs
before rerendering. Geometry, pivot, travel or nearby layout changes invalidate
the affected articulation evidence; mass/friction-only edits do not. Lighting
changes call for affected illumination views, not every isolated articulation.

Actually inspect generated images. Successful rendering, polygon counts and
zero sampled intersections do not establish correct appearance or usable cavities.
Check illumination with formal lights and representative enclosed room views;
diagnostic fill lights and removed ceilings must not mask insufficient lighting.

Overwrite stable filenames such as review/washer_open.png. Keep brief current
findings and evidence links in review/report.json, including the reason reused
evidence remains applicable. Do not add hashes, cache databases or per-iteration
reports. At delivery, close evidence gaps and review affected global views;
unchanged accepted assets do not require another set of articulation images.
If a script unconditionally renders everything, add selection/build-only controls
before using it for local iterations instead of repeatedly invoking its full loop.
