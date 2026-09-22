# Isaac Sim deformable extension

This extension authors soft bodies and cloth with Blender geometry and host-side
OpenUSD. Volume assets specify a source mesh and generation parameters; the platform
generates simulation and collision mesh data before simulation. Asset production
delivers that recipe with geometry, materials and bind declarations. Surface assets
carry an explicit triangle simulation mesh.

## Build

Add to `specs/physics.yaml`:

```yaml
extensions:
  isaacsim: isaacsim.yaml
```

Start from `templates/isaacsim.yaml`, select a target profile and reference registered
scene objects. Use the ordinary Blender and host Python environment:

```bash
.venv/bin/python scripts/run_blender.py workspaces/demo/specs/scene.yaml
.venv/bin/python scripts/export_scene.py workspaces/demo
```

The pipeline validates configuration and source geometry, authors typed USD properties,
and reopens the final candidate for offline checks before transactional publication.

## References

- [Compatibility](compatibility.md): target schema profiles and NVIDIA sources.
- [Asset contract](asset-contract.md): hierarchy, geometry, rest/bind state and attachments.
- [Materials and contact](materials-and-contact.md): units, examples and tuning.
- [Validation](validation.md): checks appropriate to each authored representation.
- [Examples](../../examples/isaacsim_deformables/README.md): elastic block and pinned cloth.

## Organization and output

`src/embodied_scene/integrations/isaacsim/` owns configuration, schema declarations,
mesh preparation, materials, attachments and offline checks. The shared publisher
owns packaging; common gravity and units remain in `physics.yaml`.

Keep editable inputs in `input/`, `specs/` and `source/`. Build outputs are
`build/scene.blend`, selected review images, one `review/report.json`, and
`exports/scene.usdc` with only referenced `textures/`. Geometry and binding
declarations belong inside USD; interchange files use temporary storage.
