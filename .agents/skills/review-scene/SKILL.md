---
name: review-scene
description: Validate and visually review a generated embodied-AI Blender scene. Use when Codex needs to add diagnostic cameras and lighting, render intermediate views, inspect a report, identify geometric or task-level defects, or plan source-level repairs.
---

# Review scene

1. Read the task and scene specifications before inspecting appearance.
2. Run deterministic validation and save `review/report.json`.
3. Render overview, top, and task views using the removable `__REVIEW__` collection.
4. For a multi-room or articulated interior, read
   [references/interior-review.md](references/interior-review.md), render the
   required room and articulation evidence, and review it before accepting the
   global views.
5. Check, in order: missing required entities, invalid transforms, task clearances, spatial containment, scale, visibility, geometry defects, and visual quality.
6. Classify findings as blocking, major, or cosmetic and cite the affected semantic identifiers.
7. Propose changes to YAML or Blender Python, not opaque manual edits.
8. Rebuild from a clean scene after repairs and retain each review iteration separately.

Escalate to Blender MCP only when reports and diagnostic renders cannot isolate the issue. Synchronize every accepted MCP edit back to source.
