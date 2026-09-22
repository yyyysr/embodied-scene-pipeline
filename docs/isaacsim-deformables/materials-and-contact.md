# Materials, contact and solver settings

Keep three kinds of information separate: physical intent, backend-supported
properties, and numerical settings. `source` is required on each material: identify
measurements, literature, user input or an uncalibrated demonstration. A material
name such as rubber or cotton alone is insufficient evidence for parameters.

## Material setup

| Config | Units / repository policy |
| --- | --- |
| `youngs_modulus_pa` | Pa; positive |
| `poissons_ratio` | dimensionless; this initial profile accepts 0 <= nu < 0.5 |
| `density_kg_m3` | kg/m³; positive when used |
| `dynamic_friction` | dimensionless; nonnegative, not capped at one |
| `surface_thickness_m` | meters; required for surfaces |
| `bend_stiffness_pa` | nonnegative Pa or explicit `isotropic_shell` policy |
| `elasticity_damping_per_s`, `bend_damping_per_s` | s⁻¹; nonnegative; bend is surface-only |

For an isotropic shell initialization, the writer computes
`bend_stiffness = E / (12 * (1 - nu**2))`. PhysX incorporates thickness in the
bending response. Do not multiply this input by thickness cubed again.
This follows [NVIDIA's surface-material example](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/110.1/dev_guide/deformables/deformable_bodies.html#surface-deformables);
it is not a measured woven-fabric model. A numerical override supports subsequent
calibration. Zero deliberately requests no bending resistance.

Estimate density from total mass/volume. For cloth use area mass/thickness:
300 g/m² with 1 mm effective thickness gives 300 kg/m³. A 0.5 × 0.5 m sample
then weighs 0.075 kg. Thickness affects both this conversion and mechanics;
do not inflate it merely to fix collision penetration.

The examples use an uncalibrated elastic block (`E=100000 Pa`, `nu=0.4`,
`rho=1000 kg/m³`) and shell (`E=1000000 Pa`, `nu=0.3`, `rho=300 kg/m³`,
`thickness=0.001 m`, isotropic bend policy). They are construction fixtures,
not a general-purpose catalog of real materials.

For a small jelly-like volume, an illustrative starting point is
`E=15000 Pa`, `nu=0.45`, `rho=1000 kg/m³`, dynamic friction `0.3`.
This is an uncalibrated elastic-solid example. Choose stiffness from the desired
compression response and damping from rebound decay; color and translucency belong
to the separate visual material. For a hollow rubber toy, first resolve wall geometry
and material volume rather than assigning solid-envelope mass.

## Contact and numerics

Each body requires explicit `contact_offset_m > rest_offset_m >= 0`.
These are collision settings, separate from shell material thickness. A numeric
self-collision filter distance must be at least twice rest offset; `auto` leaves
the backend policy. Review thin folds and both sides of grasp contact.

The supported solver knobs map by name to PhysX attributes. Documented position
iteration default is 16 and range is [1,255]. Linear, settling, elasticity and
bend damping have units s⁻¹. Pair-update frequency changes contact refresh;
collision-iteration multiplier changes repeated contact solving. Their bounds
depend on position iterations. `auto` frequency maps to zero; surface automatic
maximum velocity maps to the backend's negative sentinel.
See [the versioned parameter reference](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/110.1/dev_guide/deformables/physx_deformable_schema.html).
For boundary ambiguities in that reference, this implementation rejects explicit
combinations outside the documented numeric bounds; it does not invent a default.

Settings not supplied use target-platform defaults. Pin the target profile because
defaults can change. The optional scene frequency defaults to
120 steps/s for these examples; this is a repository starting choice, not an
NVIDIA stability guarantee. GPU dynamics and GPU broadphase configure the shared
Physics Scene, so compare interacting rigid behavior as part of user acceptance.

## Tune against a measurement

1. Verify scale, topology, source/rest intent and absence of initial interpenetration.
2. Choose mesh resolution for contact geometry; rerun selection checks after changes.
3. Refine time step and iterations until the measured response changes acceptably little.
4. Calibrate density/mass, then elastic response from load-displacement or sag data.
5. Calibrate bending from drape and friction from a sliding/clamping test.
6. Tune damping from decay; excessive damping or sleep can hide instability.

Keep the load, duration, resolution and acceptance tolerance with the test's source
or user evidence. Parameter sweeps are optional investigations, not default build
artifacts. Record accepted settings in YAML and the evidence summary in report.json.
