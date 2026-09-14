# Generated 3D assets

Use generated meshes when agent-authored Blender geometry would be a poor fit
for a curved, organic, upholstered, or visually complex object. Precise task
surfaces and mechanisms stay authored in Blender.

## Generation modes

The FAL helper supports three explicit routes:

- `text-to-3d`: send the asset description directly to Hunyuan3D.
- `text-to-reference-to-3d`: generate a clean single-object `reference.png`
  with Nano Banana or GPT Image, then send it to Hunyuan3D.
- `source-image-to-reference-to-3d`: use generative image editing to reconstruct
  the named object from a preserved source image as a clean `reference.png`,
  then send it to Hunyuan3D. This is not a mask or segmentation pipeline.

Prefer direct text-to-3D for ordinary assets without strict appearance
requirements. Generate a reference when appearance needs review or when a
source image contains a distinctive object worth preserving. If the source
object is too small or heavily occluded, use the text-generated reference route
instead of asking the editor to invent extensive hidden geometry.

```bash
python scripts/generate_asset.py workspaces/demo \
  --asset-id ceramic_mug \
  --mode text-to-3d \
  --prompt "One white ceramic mug with a wide curved handle" \
  --dimensions 0.11 0.08 0.10
```

For a reviewable text-generated reference:

```bash
python scripts/generate_asset.py workspaces/demo \
  --asset-id ceramic_mug \
  --mode text-to-reference-to-3d \
  --prompt "One white ceramic mug with a wide curved handle" \
  --dimensions 0.11 0.08 0.10 \
  --reference-only
```

Inspect `reference.png`, then repeat the command without `--reference-only`.
The existing reference is reused and only the 3D request is submitted.

To reconstruct the appearance of an object shown in a scene reference:

```bash
python scripts/generate_asset.py workspaces/demo \
  --asset-id ceramic_mug \
  --mode source-image-to-reference-to-3d \
  --source-image input/references/tabletop.png \
  --prompt "The white ceramic mug on the left" \
  --dimensions 0.11 0.08 0.10 \
  --reference-only
```

The native Codex image-generation skill may also create the reference image.
Keep it as `reference.png` in the active iteration before running the
image-conditioned 3D step.

## Minimal outputs

A direct text generation retains only the candidate mesh:

```text
generated_assets/meshes/<asset_id>/iteration_001/
  asset.glb
```

An image-conditioned generation also retains the exact reviewed input image:

```text
generated_assets/meshes/<asset_id>/iteration_001/
  reference.png
  asset.glb
```

The pipeline does not write an asset manifest, provider response, prompt file,
thumbnail, log, or duplicate OBJ/FBX/USDZ downloads. While a FAL request is
resumable, a minimal hidden `.reference.request.json` or `.asset.request.json`
may exist. It is deleted after success or a terminal provider failure.

## Regeneration

An ordinary repeated call returns the existing `asset.glb`. An interrupted call
resumes the same request in the same iteration. New iterations are created only
after a completed candidate exists and regeneration is explicit:

- `--regenerate` creates a new GLB candidate and reuses the latest reference,
  when applicable.
- `--regenerate-reference` creates a new reference and GLB candidate.

Changing placement, scale, origin, collision geometry, or Blender materials is
not asset regeneration. If the prompt, generation mode, PBR choice, topology,
or reference should change after a completed candidate, pass the appropriate
regeneration flag.

## Hunyuan options and acceptance

The Hunyuan3D V3 endpoints default to 50,000 faces, PBR enabled, and `Normal`
generation. Optional controls are:

```text
--face-count 40000..1500000
--generate-type Normal|LowPoly|Geometry
--polygon-type triangle|quadrilateral
--enable-pbr / --no-enable-pbr
```

Every downloaded GLB is unreviewed. Import it into Blender, normalize it to the
declared meter dimensions, correct axes and origin, inspect materials and
topology, and verify task-relevant geometry. Only then set `modeling_method` to
`generated_3d` and point the existing asset/scene specification at the accepted
local `source_file`. No separate asset manifest is required.
