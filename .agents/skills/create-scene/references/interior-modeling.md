# Interior modeling

Use these requirements for multi-room architectural interiors. Derive dimensions
from the task specification, structure contract, and reference evidence; do not
reuse dimensions from an unrelated scene.

## Architectural shell

- Define floor elevation, wall top elevation, thickness, and room-side direction
  explicitly. A lower wall, soffit, railing, or level change must be intentional
  and identifiable in source.
- Build continuous wall junctions. Centerline segments that merely share an end
  point are insufficient at corners, T-junctions, crossings, and transitions
  between wall thicknesses. Extend, miter, overlap, or join the wall solids so
  neither side exposes a crack.
- Resolve the complete shell and openings before room furnishings. Keep shared
  walls single-owned by the Structure Agent.

## Doors and windows

- Treat an opening as an assembly: structural void, reveals or jambs, fixed
  frame, optional mullions, movable leaf or sash, glazing, sill, and trim where
  visible.
- Parameterize installation and operating clearances. Small mechanical gaps may
  be valid, but visible gaps require appropriate stops, seals, overlaps, or trim.
- Keep fixed frames separate from movable geometry. Place each movable origin at
  its physical hinge or translation datum and express its axis in a documented
  coordinate space.
- Check the closed leaf against the opening and frame before furnishing adjacent
  space. A visually plausible frame does not compensate for a misaligned leaf.

## Articulated casework

- Decide whether an interior can become visible in any required state. Closed,
  non-interactive background cabinetry may use simplified closed construction.
- If a door, drawer, or sliding panel opens, model the revealed cabinet cavity.
  Construct carcasses from panels or an equivalent hollow shell rather than a
  solid block behind the movable part.
- Model an operable drawer as a front, bottom, sides, and back, with dimensions
  that fit inside the carcass throughout its declared travel. Add shelves or
  partitions where the open state would expose them.
- Separate fixed carcass, movable roots, handles, and decorative parts. Record
  stable semantic ownership plus intended parent body, local axis, units, and
  motion limits without authoring physics attributes.

## Articulated appliances

- Establish moving roots, closed poses, axes, units, limits, body ownership and
  stable IDs during initial modeling. Handles and door decoration follow the door;
  control panels and seals belong to the appropriate fixed or moving assembly.
- Model the interior according to the appliance's function: refrigerator storage
  compartments and shelves; a front-loading washer's front panel with a circular
  aperture, seal, recessed open drum wall and back. A washer is not a cupboard.
- Preserve operating gaps and a usable loading opening in both visual geometry
  and collision geometry. A convex hull around a hollow shell closes its cavity;
  use separate convex parts or supported static triangle meshes as appropriate.
- Choose whether the appliance body is installed/static or movable explicitly.
  Connect a moving door to its actual body when that body is dynamic; do not
  silently immobilize an appliance merely to simplify joint authoring.

## Source quality gates

Before integration, inspect the authored source for these failure patterns:

- disconnected or overlapping wall endpoints;
- inconsistent wall tops without an explicit design reason;
- frames or leaves that do not match their registered openings;
- movable storage backed by a solid visual block;
- details placed across a doorway, drawer travel, or required navigation path.

Record uncertain interpretations in the scene specification. Do not hide a
structural uncertainty behind decorative geometry.
