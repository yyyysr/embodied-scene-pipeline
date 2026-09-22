# Offline collision proxies

Use primitives for simple rigid shapes, one hull for convex assets, and offline
CoACD for ordinary concave assets. Refine decomposition or author compound proxies
when task-critical openings need more control. Target-specific SDF is a possible
precision alternative, outside the currently implemented configuration.

## Configuration

```yaml
colliders:
  - object: plate
    approximation: coacd
    parameters:
      threshold_m: 0.003
```

`object` resolves one registered triangle mesh beneath a body Xform. It may be a
visual mesh or a dedicated collision source. `hide_visual: true` declares dedicated
geometry: USD uses guide purpose, inherited visibility and physics-only material
bindings. Shared visual/collision meshes retain their visual purpose and materials.
Keep visual decorations out of collision sources. The source must not also be
configured as another collider.

Defaults: threshold_m=0.003, preprocess_mode=auto, max_convex_hull=-1,
preprocess_resolution=50, resolution=2000, seed=0. Threshold is a candidate
construction setting, not a guaranteed surface error bound. Resolution controls
distance sampling, not voxel size. A positive hull limit is enforced across all
components; -1 is unlimited. Fixed adapter settings: merge enabled, PCA/decimation/
extrusion disabled, MCTS nodes=20, iterations=150, depth=3. Actual parameters and
preprocessing choices are summarized in review/report.json.

## Construction

Use `uv sync --all-extras`. Locked CoACD 1.0.14, trimesh and scipy run in host Python,
outside Blender and Isaac Sim. The shared export reads native Blender USD triangles,
transforms them into a meter-scale translation frame, and invokes an isolated process
with a 300-second timeout per source. Triangulate collision sources in Blender.

Coincident seams are welded, edge-connected components separated, and normals oriented.
Auto preprocessing uses off for closed positive-volume components, on otherwise.
A caught failure in auto's off path permits one on retry; explicit off is respected.
Native crashes and timeouts fail export. Preprocessing can change thin walls or holes.
No automatic bounding-box scaling is applied. Fixed versions and seed improve
reproducibility without promising bitwise equality across platforms.

Each convex part becomes an independent guide-purpose convexHull Mesh beneath
`<body>/Colliders/<source-id>/part_NNN`, with its physics material. All parts share
the original body, mass and joints. The visual source receives no duplicate collision.
The platform cooks these explicit convex shapes, without repeating concave decomposition.

Process exchange files are temporary. Parts live in exports/scene.usdc; modeling
source remains in build/scene.blend. `convexDecomposition` retains its original
platform-generated meaning. No permanent OBJ collection, cache or manifest is created.

## Review

Checks cover finite triangle geometry, degeneracy, closed positive-volume convex
output, counts, final bindings and visibility. The report includes aggregate vertex/
triangle counts and bounds deltas. Bounds agreement does not prove cavity preservation;
summed part volumes are not union volumes because convex parts may overlap.

Inspect actual USD proxies with colored overlays or sections for critical support
surfaces and openings. Keep task-specific free-space samples and tolerances in scene
source, with evidence in the existing report. Reuse unaffected appearance views.
Dynamic contact and GPU cooking compatibility require separate evidence.
