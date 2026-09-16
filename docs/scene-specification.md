# Scene specification

The scene specification is a semantic contract, not a dump of Blender state or
a second geometry language. It records what must exist, its task role, known
spatial constraints, uncertainty, and the source entry point that implements it.

## Agent-authored implementation

Simple primitive scenes may omit `implementation` and use the baseline object
builder. Complex scenes should declare `implementation.mode: blender_script`
with a script below the workspace `source/` directory and a callable entry point.
The entry point receives a thin build context and the complete scene mapping:

```python
def build_scene(context, scene_spec):
    # Use bpy and local Python modules without geometric restrictions.
    context.register(root, "stable_semantic_id", "context", members=parts)
```

The runtime owns clean-scene reset, standard collections, review rigs,
validation, rendering, and saving. The authored script owns topology, modifiers,
materials, object hierarchy, and modeling strategy.

## Irregular spaces

Do not force uncertain image evidence into exact polygons before structure work.
A floorplan may begin with `status: draft`; draft rooms require only stable IDs
and may record purpose, scale evidence, reference images, assumptions, and
confidence. The Structure Agent may inspect the reference, author and review the
Blender shell, and refine its topology iteratively.

Before Room or Asset Agents depend on the shell, the structure entry point must
register each resolved floor area as an ordered, non-self-intersecting polygon
in meters. Shared wall segments receive stable identifiers and are registered
once; openings reference those wall identifiers. The runtime writes the result
to `build/structure_contract.json`. This resolved contract, rather than an
early image interpretation, is the spatial boundary for downstream work.

Rooms marked `resolved` or `accepted` in `scene.yaml` must include a polygon and
height. Draft rooms are intentionally allowed to omit them. Accepted intent
changes still update YAML before rebuilding; discoveries made while resolving
geometry are synchronized into the accepted specification after review.

## Task geometry

Task objects require explicit dimensions, initial transforms, and semantic roles. Preserve free space around grasps, doors, drawers, robot bases, and navigation paths. Decorative objects may use looser constraints.

Generated asset candidates use non-overwriting iteration directories only when
an explicit regeneration follows a completed candidate. Ordinary reruns reuse
the current result and interrupted requests resume in place. After Blender
normalization and review, an accepted asset records its local GLB:

```yaml
id: ceramic_mug
role: task
modeling_method: generated_3d
source_file: generated_assets/meshes/ceramic_mug/iteration_001/asset.glb
dimensions: [0.11, 0.08, 0.10]
position: [0.0, 0.0, 0.8]
```

The provider file is never authoritative for scale, collision, or articulation.
See `docs/generated-assets.md`.

## Optional static backgrounds

The `world` mapping records a resolved background decision, not an automatic
instruction to call a provider. A 3DGS selection names the accepted local input
image and full-resolution local SPZ. Generated provider URLs and credentials do
not belong in scene intent.

```yaml
world:
  background_intent: auto
  background_mode: 3dgs
  background_decision: use_clean_plate
  background_input: generated_assets/backgrounds/iteration_001/clean_plate.png
  background_asset: generated_assets/backgrounds/iteration_001/world_full_res.spz
  environment_image: generated_assets/backgrounds/iteration_001/world_pano.png
```

See `docs/background-generation.md` for the decision and preprocessing gates.

When the background has been aligned to explicit geometry, `assembly` records the
only accepted transform. Source correction and scene placement are deliberately
separate: the former converts the generated asset into the standard meter/Z-up
frame, while the latter places that corrected asset around the fixed task scene.

```yaml
assembly:
  version: 1
  background:
    preview_asset: generated_assets/backgrounds/iteration_001/world_100k.spz
    source_to_world:
      orientation_xyzw: [0, 0, 0, 1]
      meters_per_source_unit: 1
    placement:
      position_m: [0, 0, 0]
      orientation_xyzw: [0, 0, 0, 1]
      uniform_scale: 1
```

These identity values are examples, not an assertion that a generated world is
already aligned. The Scene Director must inspect combined evidence before adding
or accepting this mapping. `preview_asset` affects browser performance only; final
delivery always uses `world.background_asset`.

## Identity

Use lowercase snake-case identifiers in specifications and copy them to Blender custom properties. Names must remain stable across rebuilds so later physics metadata can target objects reliably.
