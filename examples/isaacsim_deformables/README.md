# Deformable construction examples

```bash
.venv/bin/python examples/isaacsim_deformables/init_workspace.py soft_block_demo --kind soft_block --profile isaacsim_6_1
.venv/bin/python scripts/run_blender.py workspaces/soft_block_demo/specs/scene.yaml
.venv/bin/python examples/isaacsim_deformables/init_workspace.py hanging_cloth_demo --kind hanging_cloth --profile isaacsim_6_1
.venv/bin/python scripts/run_blender.py workspaces/hanging_cloth_demo/specs/scene.yaml
```

Set `BLENDER_BIN` for Blender. The host Python environment authors and checks USD.

The 20 cm block declares a source mesh, hex resolution 6 and separate simulation/
collision TetMesh nodes. The platform generates their arrays before simulation.
The 50 cm cloth carries a 20 × 20 triangle grid, isotropic shell material and two
explicit corner attachments to an independent Xform.

Material values are uncalibrated construction examples. See
[materials](../../docs/isaacsim-deformables/materials-and-contact.md) for units and
selection. Output follows the single-USD scene delivery contract.
