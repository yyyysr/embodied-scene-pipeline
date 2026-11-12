# Scene delivery contract

Model in Blender, author physical intent in `specs/physics.yaml`, and deliver one
`exports/scene.usdc` plus its referenced `textures/`. Isaac Sim visual/dynamic
validation belongs to the user and remains `pending_user` until actually checked.

## Entry points

For optional Isaac Sim soft bodies and cloth, read
[the deformable extension](isaacsim-deformables/README.md). It has separate
specification and offline authoring code, sharing units, ownership checks and this
transactional publisher. Volume assets declare source meshes and generation settings;
the platform generates their simulation geometry before simulation. Surface assets
carry explicit triangle simulation meshes. Deformables own their physics hierarchies.

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
Both entry points export cameras by default, including review cameras; pass
`--exclude-cameras` to omit all cameras. Diagnostic lights remain excluded.
Orthographic review cameras retain their projection in USD; Blender's native
exporter writes perspective cameras directly.
`export_scene.py --blend ... --physics ...` supports an existing prepared scene.

## Source responsibilities

- Preserve original requests in input/. Scene/task YAML describes intent; physics
  YAML separately describes body membership, mass, collision, physics material and joints.
- Establish surface-material intent in the scene description/source and formal
  lighting in `specs/lighting.yaml` before modeling. Resolve generated materials
  using [generated-assets.md](generated-assets.md#material-intent-and-normalization)
  and lighting using the [formal lighting guidance](../.agents/skills/create-scene/references/lighting.md).
  Keep target USD settings distinct from Blender preview parameters.
- Register semantic entities with `context.register` and address internal bodies,
  colliders and anchor Empties with `context.register_reference(..., owner=entity_id)`.
  Entity IDs and reference IDs share a unique namespace; USD object names use those
  IDs. Collection groups and object parents are retained;
  the first alphabetical collection owns objects linked into multiple collections.
- Parent each moving part's meshes beneath a single rigid root. Registration adds
  metadata, not parenting. Nested rigid roots are unsupported. Moving roots and
  joint anchors must have unit world scale, no shear/reflection.
- Keep actual lights outside __REVIEW__. Diagnostic lights are excluded from delivery.
  A light existing in USD does not prove adequate brightness or lack of occlusion.
- Export frame 1 as a static snapshot. Restore complete geometry hidden for cutaway
  review. Procedural Blender shaders may need baking; do not claim visual fidelity
  from a material binding check alone. Never use preview animation as joint physics.

## Physics configuration

Use templates/physics.yaml and schemas/physics.schema.json. Object references use
registered entity or internal reference IDs rather than saved USD paths. Existing
semantic IDs remain supported. Shared material defaults can be overridden per
body or collider. Body classifications are explicit in the specification.

Static architecture and mounted objects receive collision only, no mass.
Dynamic/kinematic bodies require positive mass_kg. Kinematic motion must be supplied
by the simulator. Colliders explicitly reference a mesh or a root containing one
mesh, within their body. `none` triangle meshes are static-only in this pipeline;
supported dynamic approximations are convexHull, coacd, convexDecomposition, boundingCube
and boundingSphere. Total mass is configured;
center of mass and inertia are currently derived by the simulator.

### Entity and representation hierarchy

A semantic entity identifies a task or scene object. A rigid root identifies the
parts that move together. Visual and collision geometry are representations owned
by that entity; internal reference IDs make them addressable without assigning
them independent task roles. Each independently simulated particle can retain its
own entity and rigid root.

For an asset with dedicated proxies, organize `Visual` and `Colliders` as sibling
groups beneath its rigid root. The author creates these groups and parents the
parts in Blender; registration only adds identity and ownership metadata. Collision
pieces remain descendants of the rigid root through the `Colliders` group. An
articulated entity may contain several sibling rigid roots, each with its own
representations.

A mesh can also provide both appearance and collision directly. Use this shared
mesh when its geometry is a suitable input to the chosen approximation. Dedicated
proxies provide independently authored contact geometry where useful.

### Choosing collision geometry

Choose geometry according to the required contact surface, functional free space
and simulation cost. Collider count follows those requirements. Unless the user
specifies otherwise, apply the following defaults:

| Shape and contact needs | Representation |
| --- | --- |
| Box-like or spherical objects | boundingCube or boundingSphere on the mesh |
| Basic cylinders | Simple convex cylinder mesh with convexHull (no boundingCylinder enum) |
| Other ordinary assets, convex or concave, static or moving | Offline coacd on a suitable triangle mesh |
| Task-critical openings and interiors | Inspect/refine CoACD output or author compound proxies |
| Precision fits, e.g. threaded nuts/bolts or tight insertions | Prefer target-specific SDF; requires separate backend integration |

Use [offline collision proxies](collision-proxies.md) for parameters and inspection.
`coacd` generates explicit convexHull parts during export; `convexDecomposition`
retains its platform-side meaning. Static status alone does not justify Triangle
Mesh. Basic shapes use simple colliders; other ordinary assets default to CoACD,
including when contact precision is unspecified or low. If CoACD fails,
`convexDecomposition` is an allowed fallback without an additional user request.
Update physics.yaml and record the reason in review/report.json. The exporter
does not automatically change algorithms at runtime. Fallback geometry must still
preserve functional space and pass review; refine decomposition or author compound
proxies when needed. SDF's current implementation limits are described below.

Dedicated collision proxies use `hide_visual: true`: Blender excludes them from
appearance previews; USD authors `purpose = guide`, `visibility = inherited` and
physics-purpose material bindings. This convention applies equally to static,
dynamic and kinematic bodies. Viewers filter guide geometry from ordinary appearance
and can enable it for inspection. Physics APIs independently enable collision.
Shared visual/collision meshes use `hide_visual: false` (the default), retain their
visual purpose and surface materials, and additionally bind a physics material.
CoACD-generated parts always use the dedicated guide representation.

For precision fits targeting PhysX, a collider may explicitly set `contact_offset_m`
and `rest_offset_m` (default 0 when contact is specified). Contact must exceed rest;
choose the sum of paired offsets below the intended free assembly gap. These map
to PhysxCollisionAPI without changing the collision geometry. A material may set
`restitution_combine_mode` to average/min/multiply/max through PhysxMaterialAPI;
for example a bouncing ball can select max to retain its restitution against a
low-restitution support. Unspecified settings retain platform defaults. Other
backends may ignore these explicitly PhysX-specific properties.

### SDF intent, USD representation and engine support

SDF is preferred for precision contact where convex approximation would erase
threads, narrow passages or fitting surfaces. This choice expresses contact needs;
it does not by itself select PhysX or guarantee that a particular resolution meets
the task's tolerances.

Keep three layers distinct:

| Layer | Responsibility | Current status |
| --- | --- | --- |
| Repository configuration | Express the intended collision method independently of the engine | `sdf` is not yet accepted by physics.yaml's schema |
| Base OpenUSD physics | Describe portable collision geometry and mesh approximation | No standard SDF collision approximation |
| Target engine extension | Interpret SDF settings and generate/use collision data | No SDF export mapping implemented in this repository |

Base `UsdPhysics.MeshCollisionAPI` defines `none`, `convexDecomposition`,
`convexHull`, `boundingSphere`, `boundingCube` and `meshSimplification`.
It does not define `sdf`. See the
[OpenUSD API reference](https://openusd.org/dev/api/class_usd_physics_mesh_collision_a_p_i.html).
The repository supports a subset of these standard options plus its offline
`coacd` operation, which exports explicit standard convexHull parts. Consequently,
the repository's configuration values and OpenUSD's standard tokens are not the
same list.

USD can store an engine-specific `sdf` token, applied API names and custom
attributes. Storage alone does not give them portable simulation semantics;
the consuming engine must recognize them. Likewise, OpenUSD's `Sdf` module name
does not indicate support for signed-distance-field collision.

For a future SDF configuration, the intended design is an engine-independent
`approximation: sdf` selection with explicit target-backend mapping:

- For Isaac Sim / PhysX, author the target version's SDF collision selection,
  `PhysxSDFMeshCollisionAPI` and resolution/cooking parameters. The engine can
  generate the SDF during collision cooking; offline SDF computation in this
  repository is not a prerequisite. See NVIDIA's
  [collision guide](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/110.0/dev_guide/rigid_bodies_articulations/collision.html)
  and [SDF schema reference](https://docs.omniverse.nvidia.com/kit/docs/omni_usd_schema_physics/latest/physxschema/class_physx_schema_physx_s_d_f_mesh_collision_a_p_i.html).
- For other engines, use their supported SDF extension or import convention;
  do not assume they understand PhysX attributes.
- For a base-OpenUSD-only target, report SDF as unsupported rather than claiming
  a custom token is a portable SDF collider.

This describes the extension boundary, not an implemented YAML option. Until
schema, authoring and validation support are added, do not write `approximation:
sdf` into executable physics.yaml or claim that SDF has been exported. Record
the precision requirement and support gap in scene/task specifications and the
existing review/report.json. Any alternative representation must be checked
against the required clearance/contact geometry. Static attribute validation
cannot establish cooking success, contact accuracy or dynamic stability; those
remain pending user validation in the target simulator.

### Joints

Fixed, revolute and prismatic joints connect dynamic body1 to optional body0.
An omitted/static body0 attaches to world. `anchor` supplies the initial world joint
frame; axis is X/Y/Z in that frame. The authored pose is coordinate zero and must
lie within limits. Revolute limits/targets are degrees, prismatic values meters;
velocities are degrees/s or m/s. An optional force drive specifies stiffness,
damping and max_force. Zero stiffness allows passive damped motion. Engine-specific
rigid-body damping, articulation roots and nonzero initial joint coordinates are
not authored by this version. Connected-body collision settings do not justify
removing surrounding collisions to hide installation defects.

## Appearance mapping

Use native Blender USD export for supported material and lighting data. Apply
any required target-renderer mapping reproducibly through the shared delivery
pipeline, before final validation/publication. The resolved material and lighting
intent controls this mapping; file-format fallbacks and Blender preview powers
are not target-renderer specifications.

The formal lighting guidance defines default environment attributes and explicit
overrides. An untextured environment uses direct light color/intensity attributes
and has no effective texture asset, including through composition. Only textures
referenced by the final delivery belong in `exports/textures/`.

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

Appearance acceptance additionally compares the effective bound shaders and
lighting against the resolved source/specification:

- Surface metallic response, roughness, color/normal texture connections, UVs
  and color spaces express the intended materials, including mixed-material assets.
- The environment's type, color, intensity, exposure, color-temperature setting
  and texture presence match its resolved configuration; local lights match
  their specified placement and output settings.
- Referenced texture assets resolve, and untextured environments have no effective
  environment texture binding.

These are authoring/review requirements, not a claim that `validate_usd.py`
automatically compares workspace appearance intent. Inspect the final USD for
them and record the result in the same review/report.json. Attribute conformance
and visual acceptance in the target renderer are recorded separately.

The user opens scene.usdc in Isaac Sim, verifies lighting/materials and collisions,
then tests settling, joint travel and task interaction. Static checks do not certify
simulation stability, full-range clearance, robot usability or rendering. Repair
source/configuration and rebuild; never accept a simulator-only edit as the source.

Older export_usd.py and author_physics.py commands are compatibility names for the
new export_scene.py interface (workspace argument), not separate export stages.
