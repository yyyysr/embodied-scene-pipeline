# Initial scene lighting

Choose useful formal lighting during modeling. Record the intended renderer and
keep environment and room-light settings together in the workspace specification
(for example specs/lighting.yaml), with defaults and explicit room overrides.
Use the same source settings on subsequent exports; avoid simulator-only fixes.

## Choosing the initial setup

- Establish environment lighting and room lighting separately. Environment light
  supplies exterior illumination and light through openings; enclosed rooms need
  their own fixtures. Diagnostic lights must not substitute for formal lighting.
- Size the room-light setup for room area, ceiling height, fixture count and
  placement. A larger room may need multiple fixtures or greater output rather
  than the same single light and intensity used in a small room.
- Consider light type, intensity, exposure, emitting area and normalize together.
  USD exposure zero is neutral (the multiplier is 2^exposure). With normalize
  disabled, changing emitter area also changes total output. Blender light power
  and USD intensity are not interchangeable numbers across renderers.
- Keep emitting surfaces outside opaque fixture geometry, walls and ceilings;
  orient them toward the intended space. Increasing intensity cannot fix an
  incorrectly placed or obstructed emitter.
- An environment EXR contributes color and directional radiance; intensity and
  exposure scale it. EXR format alone does not imply a bright HDR environment.
  A one-pixel color texture is a uniform environment, not a detailed sky HDRI.
- Start from settings previously accepted under comparable renderer, exposure,
  texture and light-size conditions. Record those conditions and distinguish
  user-confirmed values from provisional tuning. Do not mandate one universal
  intensity for every renderer or environment map.

## Apartment experience

In apartment_rebuild, Blender World strength 0.3 exported to a DomeLight with a
one-pixel blue-gray EXR. The user found it ineffective as environment fill in
Isaac Sim and reported that intensity around 1000 gave a better effect. This is
a case-specific starting reference; camera/render exposure was not recorded.

The original room setup used RectLights with intensity 1500, exposure 0,
normalize false and 1 m by 1 m emitters. The user reported insufficient brightness,
particularly in larger rooms. Subsequent provisional intensities were 2500–15000
by room (living room 15000); these were not all visually confirmed by the user.
Reuse the lesson of renderer-aware, room-specific initialization, not these
numbers without their context.

## First visual calibration

Inspect representative small and large rooms using formal lights, intact ceilings
and intended viewing conditions. Check readable surfaces, dark corners and clipped
highlights. Keep camera/render exposure consistent while comparing light changes.
Blender appearance alone cannot certify Isaac Sim appearance: have the user check
the target renderer, then put accepted values back in the workspace source.
Rerender only affected illumination views, following review-scene's evidence reuse
rules; no separate lighting report or automatic image archive is needed.
