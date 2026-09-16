# Optional 3DGS backgrounds

3DGS is an optional visual-context enhancement, not a default for tabletop
tasks. The Scene Director classifies image evidence before any paid generation.
Task, manipulable, articulated, support, and collision-critical entities remain
explicit Blender geometry.

## Decision gate

After task and scene semantics are separated, classify the reference as one of
`blank`, `task_only`, `simple`, or `rich_static` and resolve the user's intent as
`none`, `auto`, or `required`.

- Skip 3DGS for no reference, blank backgrounds, task-only images, or context
  that Blender can express cheaply.
- Use a clean reference directly when it contains useful static context and no
  people, hands, robots, task entities, or explicit task-support geometry.
- Create a clean plate when useful context exists but excluded entities remain.
- Skip or ask for better evidence when cleanup would hallucinate most of the
  environment.

Record the resolved reason in `scene.yaml`; do not infer it again during build.

## Clean-plate contract

Preserve the source image under `input/references/`. A derived clean plate goes
under the selected `generated_assets/backgrounds/iteration_NNN/` directory.
It must preserve image dimensions, aspect ratio, camera viewpoint, perspective,
architectural boundaries, and lighting while removing explicitly enumerated
people, robots, task objects, task-support surfaces, and transient clutter.

The native Codex path may edit the reference with the image-generation skill and
save the result as `clean_plate.png`. For a scriptable path, export `FAL_KEY` or
set it in the ignored repository-root `.env`, then run either supported FAL alias:

```bash
python scripts/prepare_background.py workspaces/demo clean-plate \
  --image input/references/source.png \
  --provider nano-banana \
  --prompt "Preserve the camera and static room; remove the enumerated task entities."
```

`gpt-image-2` is also accepted as `--provider`. Both backends must produce the
same `clean_plate.png` contract. An agent must visually accept that image before
it is submitted to 3DGS.

## World generation

Export `WORLD_LABS_API_KEY` or set it in the ignored repository-root `.env`, then
use an accepted clean plate or an already clean original reference:

```bash
python scripts/prepare_background.py workspaces/demo world \
  --image generated_assets/backgrounds/iteration_001/clean_plate.png \
  --prompt "An empty static laboratory environment with no task entities."
```

When the input is already inside an iteration directory, the world command uses
that same directory by default. For a clean original reference it creates the
next iteration; `--output` may select an existing iteration explicitly.

The World Labs adapter downloads local files with fixed names:

```text
world_full_res.spz       required
world_500k.spz           optional
world_150k.spz           optional
world_100k.spz           optional
world_collider.glb       optional reference only
world_pano.png           optional
world_thumbnail.webp     optional
```

No background-specific final manifest is written. A minimal hidden request file
exists only while an API request can be resumed and is deleted after successful
downloads. The filesystem stores results, `scene.yaml` selects the accepted
SPZ/input, the existing build manifest records that selection, and the existing
review report checks that selected local files exist and are non-empty.

## Failure policy

Optional background failure is a major review finding, not a task-blocking
geometry defect. Switch `background_mode` to `blender` or `none` and rebuild.
When the user explicitly requires the background, retain the failed iteration
and request better evidence or retry instead of silently accepting a fallback.

World generation does not establish scale or placement. After explicit geometry
exists, follow `docs/scene-editor.md` to align the selected SPZ and deliver the
combined USD. Provider collider geometry may aid visual placement but is never
task collision truth.
