# Scene assembly editor

The local editor previews SPZ with Spark and Blender geometry with Three.js.
It edits only the background assembly in `specs/scene.yaml`. It does not run physics.

## Run

```bash
uv sync --extra editor --extra dev
npm --prefix apps/scene-editor ci
npm --prefix apps/scene-editor run build
uv run --extra editor python scripts/edit_scene.py workspaces/kitchen_tabletop_manipulation --blender /path/to/blender
```

Open `http://127.0.0.1:8765`. Blender must be compatible with the saved `.blend`.
The server prepares a temporary GLB on first opening. Preview generation does not
save the blend file. Files are removed when the server stops.

For frontend development, run `npm --prefix apps/scene-editor run dev` alongside
the Python server. Vite proxies `/api` to port 8765. Production needs only Python
and the already-built frontend.

## Placement

The worktop stays fixed. Move/rotate the background with the gizmo or numeric
fields; adjust uniform scale numerically. Grid spacing is 0.5 m. Coordinates and
distances are meters. Save writes only the assembly configuration into the existing
scene YAML, preserving comments. Reload and undo are available. An external YAML
edit causes a save conflict instead of being overwritten.

The source-axis panel is separate from placement. An identity default means
**uncalibrated**, not verified orientation. Correct the source axes first, then
adjust background scale, floor height and placement. The smallest available
100k/150k/500k variant is the initial preview choice; the dropdown changes preview
quality without changing delivery quality. The final source remains
`world.background_asset`; resolutions must share the same source coordinate frame.

The expanded source-axis panel provides explicit -Y-up, +Y-up and +Z-up presets.
Each replaces the source rotation (it does not accumulate rotations), leaving
placement and unit scale unchanged. -Y-up uses Rx(-90 degrees), mapping
source (x,y,z) to world (x,z,-y). This is separate from the GLB Rx(+90 degrees).
The kitchen workspace records this correction based on its reference and inspected
SPZ projections. Its scale, floor height and placement still require manual review;
a saved assembly is editable state, not proof of completed alignment.

## Agent alignment procedure

Alignment is a Scene Director task performed after the SPZ and explicit Blender
scene exist. It is an evidence-guided rigid placement, not an image-registration
solver. A single source image or a clean plate generally does not contain enough
information to recover an exact metric transform automatically.

The explicit task geometry is authoritative. Keep its meter/Z-up coordinates and
all relative object poses fixed; transform the static background as one unit.
The agent should:

1. Build `build/scene.blend`, validate its scale and clearances, then start the
   editor. The server creates only a temporary GLB preview.
2. Load the lowest available SPZ resolution and show only the background. Determine
   its vertical direction and handedness from floors, cabinet edges, walls and
   gravity cues. Set `source_to_world` once. Begin with 90-degree rotations when
   the source axis convention is unknown. Do not use scene placement to conceal an
   axis error.
3. Show both assets. Calibrate scale from defensible evidence such as measured room
   geometry, standard-height counters corroborated by several features, doors, or
   a provider reference mesh. A generated stage declaring meters is not evidence
   that reconstruction scale is metrically correct.
4. Adjust background yaw and translation so the explicit task support occupies the
   intended free area and agrees with the source composition. Use top, front, side
   and perspective views. Keep pitch and roll at zero after source correction unless
   the reference provides strong contrary evidence.
5. Check that static background imagery does not visibly duplicate task objects or
   cut through the worktop and manipulable objects. Provider collision remains a
   placement aid only and is excluded from task physics.
6. Compare the combined view with all applicable input references. When background
   and task references have different cameras, accept a spatially plausible
   composition; do not claim camera-derived registration or precise room dimensions.
7. Save once the source frame, relative scale, support placement and task-facing
   views are coherent. Saving writes the two transforms into `specs/scene.yaml`.
   Reopen the editor and verify that the same composition is reconstructed.
8. Export and inspect the actual `exports/scene.usdc`. Confirm one Gaussian field,
   unchanged task-body/collider counts, meter/Z-up stage metadata, resolved assets,
   and the expected nested background transforms. Isaac Sim dynamics remain a user
   validation step.

The Agent may operate the editor interactively or through local browser automation
and screenshots. In both cases the accepted numbers must live in `scene.yaml`; a
browser-only transform is not a completed alignment. If scale or placement lacks
adequate evidence, report that uncertainty rather than representing it as measured.

For the kitchen workspace specifically, the marble worktop and its objects remain
fixed. The agent places the static kitchen around that foreground island. Because
the background reference excludes the island and uses a different composition from
the task reference, the result is semantic/visual alignment rather than recovered
camera registration.

Save before exporting. The editor calls the shared Blender/USD/pxr delivery and
preserves an existing `source/usd_settings.py:configure_stage` callback. A normal
workspace rebuild also composes the background when `assembly` is present.
Without `assembly`, existing export behavior is unchanged.

## Coordinate contract

All world coordinates are right-handed, meter, Z-up. Quaternions are saved as
`[x,y,z,w]`; UI Euler angles use Three.js intrinsic XYZ order in degrees. Positive
uniform scales only. Column-vector notation:

```
p_world = T(placement) R(placement) S(placement) R(source) S(source) p_raw
```

The exact same two nested transforms are authored as USD Xforms. USD/Gf quaternion
construction explicitly rearranges xyzw to wxyz. Matrix arrays are not copied
between Three.js and Gf.

Blender preview exports use glTF Y-up and receive exactly one `Rx(+90°)` inverse
on loading into the Z-up viewer. Semantic IDs, origins and parent relationships
are retained. There is no asset centering or arbitrary display scale.

SPZ is loaded without a display flip. `source_to_world` supplies any necessary
axis correction and unit conversion. `usd-convert-gsplat` writes source-local
Gaussian positions, orientations, scales and SH; it does not bake placement.
Setting USD `upAxis` alone does not rotate coordinates. Do not copy image-blaster's
default 180° X rotation without verifying the source.

## Delivery and checks

The final `exports/scene.usdc` embeds the Gaussian field and interactive geometry,
materials, lights and physics. It no longer references an SPZ or intermediate USD.
Image textures remain sibling resources; a literally single-file texture package
would require a separate USDZ delivery mode, not implemented here.

The flattened final stage is represented as:

```text
/World                                      (default prim, meter, Z-up)
  /BackgroundPlacement                      (user placement: T · R · S)
    /SourceToWorld                           (fixed source-axis/unit correction)
      /Splat                                 ParticleField3DGaussianSplat
        positions, orientations, scales, opacities, spherical harmonics
  /collection_structure                     explicit worktop/support geometry
  /collection_task                          explicit manipulable assets
  /LIGHTING                                  formal delivered lights
  /PhysicsScene                              gravity and physics scene
  ...                                        materials, colliders and rigid bodies
```

Publishing flattens the temporary Gaussian USD reference, so the final USDC contains
the Gaussian arrays directly and does not depend on the source SPZ or an intermediate
background USD. The placement Xforms remain authored and inspectable rather than
baking the alignment into millions of points. Explicit task geometry retains its
semantic hierarchy and pxr-authored physics.

“One combined scene file” therefore means one authoritative `scene.usdc` containing
both 3DGS and explicit scene/physics data. Raster material textures are still the
documented sibling `exports/textures/` resources. If delivery must be literally one
filesystem file including textures, add a USDZ packaging mode; current delivery does
not claim that property.

Existing static USD checks are extended with Gaussian array/SH checks and transform
validation. Python and TypeScript test the same asymmetric coordinate example.
Preview lighting is for placement; it is not a simulation or material-fidelity
certificate. Isaac Sim dynamic validation remains `pending_user`.

```bash
uv run --extra editor --extra dev pytest tests/test_assembly.py tests/test_editor.py tests/test_usd_delivery.py
npm --prefix apps/scene-editor test
```

For a real Spark decoding and save/reload browser test (mock assets; no workspace
writes), run from `apps/scene-editor`:

```bash
npx playwright install chromium --only-shell
npm run test:browser
```

This test uses software WebGL and an asymmetric Gaussian with a nonidentity
orientation. Spark and USD are checked against the same source-space fixture.

The design borrows image-blaster's separate background/asset transforms and manual
placement workflow. The implementation does not copy its rendering patches,
physics approximations, source recentering, or scene JSON persistence.

## Estimate floor height

After correcting source axes, click **估算地面并对齐 Z=0** to estimate a low,
spatially broad horizontal band from the currently displayed SPZ. The backend
uses the submitted (including unsaved) source and placement transforms, filters
low-opacity/non-finite points, and searches the lower robust height range for
bands with sufficient two-dimensional coverage. Sparse low outliers do not define
the floor. Missing evidence returns an error instead of a bounding-box fallback.

The result adjusts only background placement Z in the browser, supports undo,
and requires Save for persistence/export. It can move the background up or down;
repeating with unchanged geometry leaves the estimated floor at Z=0. Correct axes
first and rerun after changing scale or rotation. This is an approximate geometric
suggestion: a low platform can be mistaken for a floor, tilted/partial floors may
be rejected, and Gaussian tails or noise can remain below the grid. Interactive
geometry and physics are never changed. No estimate is applied on page load.
