# Scene delivery contract

Model in Blender, author physical intent in `specs/physics.yaml`, and deliver one
`exports/scene.usdc` plus its referenced `textures/`. Isaac Sim visual/dynamic
validation belongs to the user and remains `pending_user` until actually checked.

## Entry points

```bash
# Build, review, export and author physics in one pipeline:
.venv/bin/python scripts/run_blender.py workspaces/demo/specs/scene.yaml
# Existing modeled scene, same export/physics pipeline:
.venv/bin/python scripts/export_scene.py workspaces/demo
# Inspect the actual final USD; print results without another file:
.venv/bin/python scripts/validate_usd.py workspaces/demo/exports/scene.usdc
```

Set `BLENDER_BIN` to the executable. `run_blender.py --geometry-only` explicitly
stops before USD delivery. Default builds require a valid neighboring physics.yaml;
missing physics must not silently produce a supposedly simulation-ready scene.
`export_scene.py --blend ... --physics ...` supports an existing prepared scene.

## Source responsibilities

- Preserve original requests in input/. Scene/task YAML describes intent; physics
  YAML separately describes body membership, mass, collision, material and joints.
- Assign unique semantic IDs to referenced roots, colliders and anchor Empties.
  USD object names use those IDs. Collection groups and object parents are retained;
  the first alphabetical collection owns objects linked into multiple collections.
- Parent each moving part's meshes beneath a single rigid root. Registration adds
  metadata, not parenting. Nested rigid roots are unsupported. Moving roots and
  joint anchors must have unit world scale, no shear/reflection.
- Keep actual lights outside __REVIEW__. Diagnostics are excluded from delivery.
  A light existing in USD does not prove adequate brightness or lack of occlusion.
- Export frame 1 as a static snapshot. Restore complete geometry hidden for cutaway
  review. Procedural Blender shaders may need baking; do not claim visual fidelity
  from a material binding check alone. Never use preview animation as joint physics.

## Physics configuration

Use templates/physics.yaml and schemas/physics.schema.json. References are semantic
IDs rather than saved USD paths. Shared material defaults can be overridden per
body or collider. Do not guess missing body classifications from object names.

Static architecture and mounted objects receive collision only, no mass.
Dynamic/kinematic bodies require positive mass_kg. Kinematic motion must be supplied
by the simulator. Colliders explicitly reference a mesh or a root containing one
mesh, within their body. `none` triangle meshes are static-only; supported dynamic
approximations are convexHull, boundingCube and boundingSphere. Model compound
convex proxies when a hull would close an interior or hand-access gap. Mark proxy
meshes hide_visual=true; keep visual meshes as siblings. Total mass is configured;
center of mass and inertia are currently derived by the simulator.

Fixed, revolute and prismatic joints connect dynamic body1 to optional body0.
An omitted/static body0 attaches to world. `anchor` supplies the initial world joint
frame; axis is X/Y/Z in that frame. The authored pose is coordinate zero and must
lie within limits. Revolute limits/targets are degrees, prismatic values meters;
velocities are degrees/s or m/s. An optional force drive specifies stiffness,
damping and max_force. Zero stiffness allows passive damped motion. Engine-specific
rigid-body damping, articulation roots and nonzero initial joint coordinates are
not authored by this version. Connected-body collision settings do not justify
removing surrounding collisions to hide installation defects.

## Outputs

```text
input/                  original evidence
specs/                  editable intent/configuration
source/                 scene-specific modeling
build/scene.blend        editable modeled result
review/report.json      one summary, including USD failures and pending checks
review/*.png            diagnostic views when needed
exports/scene.usdc       full geometry, materials, lights and physics
exports/textures/       only referenced resources; absent when unused
```

Create asset/provider directories only when needed. The structural handoff
build/structure_contract.json remains for resolved multi-room work because dependent
room construction consumes it; it is not a duplicate USD scene manifest.

No default hash lists, object-map files, delivery/interaction manifests, duplicate
reports, backup exports or automatic review histories. Object mappings are computed
from the current export. Blender-to-host interchange uses a temporary directory,
removed on success or failure. Physics layers stay in memory. Flattening composition
preserves object hierarchy and relationships; referenced assets are copied and
rewritten relative to the final file before publication.

`--debug` retains the current exchange directory in build/usd_debug for an actual
investigation, replacing its previous contents. It is opt-in, never a delivery
requirement. Query the final USD first; save detailed diagnostics only when needed.

The publisher replaces only a managed exports directory containing scene.usdc and
textures. If legacy/unrelated files exist it reports them, rather than silently
deleting user data. Move old files out once during migration. Failed validation
leaves the prior successful delivery untouched and updates the summary to failure.

## Acceptance

Blender geometry/review checks precede export. The export compares evaluated mesh
bounds and resolves actual semantic paths. The final USD is reopened to check units,
mesh topology, hierarchy, masses, material bindings, joint targets and initial frames,
limits and missing resources. Results are merged into review/report.json without
hashes or repeated scene data. The build fails if checks fail.

The user opens scene.usdc in Isaac Sim, verifies lighting/materials and collisions,
then tests settling, joint travel and task interaction. Static checks do not certify
simulation stability, full-range clearance, robot usability or rendering. Repair
source/configuration and rebuild; never accept a simulator-only edit as the source.

## Existing apartment migration

The apartment's prepared Blender assembly and physics.yaml remain editable sources.
Its source/build_physics.py is now a thin shared-pipeline call. The previously
accepted lighting adaptation runs as an in-memory callback; it does not emit a
lighting layer/report. This is retained solely for the existing case, not generated
for new scenes. The unresolved light-occlusion/appearance issue remains pending;
output consolidation does not change lighting parameters or certify its effect.

Older export_usd.py and author_physics.py commands are compatibility names for the
new export_scene.py interface (workspace argument), not separate export stages.
