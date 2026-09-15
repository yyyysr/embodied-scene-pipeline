# Generated 3D assets

Use generated meshes when agent-authored Blender geometry would be a poor fit
for a curved, organic, upholstered, or visually complex object. Precise task
surfaces and mechanisms stay authored in Blender.

## Generation modes

The asset helper supports three explicit routes:

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

For a local text-generated reference, select SD3.5 explicitly:

```bash
python scripts/generate_asset.py workspaces/demo \
  --asset-id ceramic_mug \
  --mode text-to-reference-to-3d \
  --prompt "One white ceramic mug with a wide curved handle" \
  --dimensions 0.11 0.08 0.10 \
  --image-provider sd35 \
  --reference-only
```

The local adapter invokes `local_runtime/sd35_worker.py` with the configured
Python interpreter. The repository does not create or manage that environment;
`EMBODIED_SCENE_LOCAL_ASSET_PYTHON` may override `asset_generation.local_sd35.python`.
The worker follows EmbodiedGen's SD3.5 Medium baseline (1024 square image, 25
steps, guidance 7) but produces one opaque reviewed reference without background
segmentation. It never falls back to a paid provider automatically.

For several references, use `LocalSD35ImageGenerator.generate_many()`. It opens
one stage-scoped worker, loads SD3.5 once, processes the requests in order, and
releases the process after the batch. `generate()` remains the isolated
single-reference interface.

To smoke-test SD3.5 without creating a workspace or calling a 3D provider, run
the worker directly with the prepared model environment:

```bash
/path/to/sd35/python local_runtime/sd35_worker.py \
  --prompt "One white ceramic mug with a curved handle" \
  --output /tmp/sd35_test.png
```

## Local TRELLIS image-to-3D

The local TRELLIS adapter targets the original `microsoft/TRELLIS-image-large`
pipeline, not TRELLIS.2. Its source is pinned as `third_party/TRELLIS`; initialize
the submodule before using the selected TRELLIS Python environment:

```bash
git submodule update --init --recursive third_party/TRELLIS
python scripts/check_local_asset_runtime.py \
  --backend trellis \
  --python /path/to/trellis/python
```

The adapter adds this checkout to the child process only. Numba and Warp caches
use a temporary session directory and are removed when the worker exits.

TRELLIS accepts either a meaningful alpha channel or a stable white-background
reference. White-background conversion is deterministic and happens in memory;
the adapter disables TRELLIS' learned Rembg preprocessing and fails when the
background contract is not satisfied. It retains neither a mask nor a condition
image.

```bash
python scripts/generate_asset.py workspaces/demo \
  --asset-id ceramic_mug \
  --mode text-to-reference-to-3d \
  --prompt "One white ceramic mug with a wide curved handle" \
  --dimensions 0.11 0.08 0.10 \
  --image-provider sd35 \
  --3d-provider trellis
```

`EMBODIED_SCENE_LOCAL_TRELLIS_PYTHON` may override
`asset_generation.local_trellis.python`. For a direct smoke test without a
workspace, use the prepared TRELLIS runtime:

```bash
/path/to/trellis/python local_runtime/trellis_worker.py \
  --image /tmp/sd35_test.png \
  --output /tmp/trellis_test.glb
```

Only the textured `asset.glb` is retained. Gaussian, raw mesh, preprocessing,
texture-baking, and preview artifacts remain in memory or temporary storage.
`LocalTrellisProvider.generate_many()` reuses one loaded TRELLIS pipeline for a
sequence of reference images; `generate()` retains the isolated single-asset
behavior.

## Agent JSONL batch interface

Agents should use one stable command instead of authoring Python invocation
scripts. The command reads all jobs from stdin by default, validates the batch,
loads the selected model once, and emits one JSON object as each job completes.

Generate several SD3.5 references in one model session:

```bash
python scripts/generate_local_batch.py --provider sd35 <<'JSONL'
{"job_id":"mug","prompt":"One white ceramic mug","output_path":"/tmp/mug.png"}
{"job_id":"bowl","prompt":"One red ceramic bowl","output_path":"/tmp/bowl.png"}
JSONL
```

Generate several TRELLIS assets in one model session:

```bash
python scripts/generate_local_batch.py --provider trellis <<'JSONL'
{"job_id":"mug","prompt":"One white ceramic mug","input_path":"/tmp/mug.png","output_path":"/tmp/mug/asset.glb","target_dimensions":[0.11,0.08,0.10]}
{"job_id":"bowl","prompt":"One red ceramic bowl","input_path":"/tmp/bowl.png","output_path":"/tmp/bowl/asset.glb","target_dimensions":[0.15,0.15,0.07]}
JSONL
```

Pass `--input /path/to/jobs.jsonl` when an existing JSONL source is more
convenient. No copy of the requests is retained. Relative input and output paths
are resolved from the current working directory. TRELLIS outputs use the
canonical `asset.glb` filename expected by scene specifications.

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
