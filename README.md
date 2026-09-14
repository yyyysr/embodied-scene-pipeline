# Embodied Scene Pipeline

Agent-native pipeline for building embodied-AI scenes with Blender. The first milestone accepts a task description, a scene description, and optional reference images; produces structured specifications and Blender Python; renders diagnostic views; and iterates from validation feedback.

## Current scope

- Native Codex/agent entry point; no public agent CLI or API yet.
- Blender Python is the source-controlled modeling path.
- Complex scenes may declare an agent-authored `source/build_scene.py` entry point;
  the primitive builder remains a backward-compatible convenience path.
- Blender MCP is optional for interactive diagnosis.
- Spatial structure and regular assets are modeled by agents in Blender.
- Complex assets may be delegated to a 3D-generation provider.
- FAL Hunyuan3D V3 can generate candidate GLB assets directly from text or
  from clean references generated with Nano Banana/GPT Image; see
  `docs/generated-assets.md`.
- Optional tabletop visual backgrounds can use a Codex image edit or FAL clean
  plate followed by World Labs; see `docs/background-generation.md`.
- Native Blender USD export and separate `pxr` physics authoring with static checks;
  Isaac Sim dynamic checks are performed by the user. See [USD workflow](docs/usd-physics.md).

## Quick start

1. Install Python 3.11+ and Blender 4.x.
2. Create a virtual environment and run `pip install -e '.[dev]'`.
3. Export `BLENDER_BIN` if Blender is not on `PATH`.
4. Run `python scripts/init_workspace.py tabletop_demo`.
5. Fill scene/task/physics YAML and the modeling source, then run
   `python scripts/run_blender.py workspaces/tabletop_demo/specs/scene.yaml`.
   This builds, reviews and delivers `exports/scene.usdc` plus textures.
   For an existing modeled scene use `python scripts/export_scene.py workspaces/<id>`.
   `--geometry-only` explicitly stops before USD; `--debug` retains USD intermediates.

For an irregular or image-derived environment, keep uncertain rooms in draft
form, declare a `blender_script` implementation, and let the structure source
register resolved rooms, shared walls, and openings. The build writes the
resulting topology to `build/structure_contract.json` before downstream room
detailing.

Or open this repository in Codex and ask:

> Read AGENTS.md and docs/project-context.md. Create the tabletop example, run validation and diagnostic renders, and report remaining issues.

## Source of truth

User input is immutable evidence. YAML specifications are scene intent. Blender Python is the reproducible implementation. Generated `.blend` files and renders are build products, not the sole source of truth.
