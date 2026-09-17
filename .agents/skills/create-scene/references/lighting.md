# Formal scene lighting

## Resolve intent before modeling

Record the intended renderer, environment lighting and local lights together in
`specs/lighting.yaml`. Resolve unspecified settings with the defaults below;
explicit user requirements and scene-specific settings take precedence. Keep
Blender preview parameters and target USD parameters separately identified so
each renderer receives a deliberate configuration.

## Default environment

Unless otherwise specified, use one untextured, neutral white DomeLight with
intensity 1000, exposure 0 and color temperature disabled. A pure-color
environment is expressed directly as light attributes, with no EXR/HDR image.

The following illustrates the resolved USD intent in the workspace lighting
specification. It is an authoring convention, not an automatically consumed
runtime schema; source/export code must implement the recorded values.

```yaml
target_renderer: Isaac Sim
usd:
  environment:
    type: DomeLight
    color: [1, 1, 1]
    intensity: 1000
    exposure: 0
    enable_color_temperature: false
    texture: null
```

When the task calls for an HDRI, a particular environment color or different
intensity, record that override explicitly. A textured environment includes its
asset path, orientation and intensity/exposure settings. A visual background
asset and the lighting environment are separate choices; selecting a background
does not by itself request an environment texture.

## Build local illumination

Environment light supplies broad ambient illumination. Add formal local lights
according to room size, openings, fixtures, occlusion and task-surface needs.
Enclosed rooms still need useful illumination when the shell is intact.

Choose light type, emitting area, orientation, intensity, exposure and normalize
together. Place emitters outside opaque fixture geometry and aim them at the
intended space. USD exposure zero is neutral; exposure scales output by
`2^exposure`. With normalize disabled, emitter area also affects total output.
Blender watts/World strength and USD intensity are distinct renderer parameters.

Keep formal lights outside `__REVIEW__`. Review cameras use formal illumination
for appearance acceptance; diagnostic lights are only for geometry inspection.

## Carry intent through delivery

Implement materials and lights in editable source and map target settings through
the shared USD delivery pipeline. For the default environment, author
`inputs:color`, `inputs:intensity`, `inputs:exposure` and
`inputs:enableColorTemperature` from the resolved specification, with no effective
`inputs:texture:file` asset. Package only textures referenced by the final scene.
When composition contains a weaker texture opinion, clear or override it so the
composed environment is actually untextured.

Inspect final USD attributes against the specification, then review representative
task surfaces and enclosed spaces in the intended renderer. Keep camera/render
exposure consistent while comparing views. Record accepted adjustments in the
specification and source, and rerender only affected evidence. Attribute checks,
Blender appearance and user-confirmed Isaac Sim appearance are distinct evidence;
record them in the existing `review/report.json`.
