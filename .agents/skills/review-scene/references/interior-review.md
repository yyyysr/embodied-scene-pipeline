# Interior review

Use this review mode for multi-room architectural scenes and for interiors with
operable doors, windows, drawers, or cabinet panels. Global renders establish
composition; they do not provide sufficient evidence for room-level acceptance.

## Evidence coverage

- Render at least one readable diagnostic view per resolved room. Add another
  view when one camera cannot show the room boundary, openings, circulation, and
  important furniture without substantial occlusion.
- Keep overview, top, and task views in addition to room views. Record every
  expected and produced view by room or task entity in the machine-readable
  report so missing coverage cannot silently pass.
- Review each room after its detailed source is integrated. Repair its source and
  rebuild before treating the global scene as complete.
- Use temporary review visibility overrides for ceilings or occluding walls.
  Restore them before saving the deliverable scene; never repair visibility only
  in generated `.blend` state.

## Architectural checks

- Compare wall top elevations against the authored structure contract. Report an
  unexplained difference rather than inferring that it is intentional.
- Inspect every corner, T-junction, crossing, and wall-thickness transition from
  both sides. Use geometry queries for endpoint closure or solid overlap when a
  render cannot prove continuity.
- For every opening, compare the registered void with the fixed frame and closed
  movable leaf. Check jamb, header, sill, center meeting, depth placement, and
  visible light leaks.
- Distinguish intentional operating tolerance from an unfinished opening. Trim,
  stops, seals, mullions, and overlapping profiles may visually close a valid
  mechanical gap.

## Casework and articulation

- Inspect closed and fully open states for every task-relevant articulation. Add
  a partially open view when it reveals a collision or ambiguous hierarchy.
- An open cabinet must reveal a cavity rather than a solid carcass. An open
  drawer must have a bottom, sides, and back and must remain inside its carcass at
  the closed limit.
- Verify the moving root, fixed parent body, local axis, units, limits, handle
  placement, and semantic ownership from Blender data, not only from names or
  YAML declarations.
- Evaluate door sweeps and drawer travel against fixed geometry and the robot's
  required approach space. Pose the actual Blender objects at their limits or
  compute swept geometry; do not mark a clearance as passed from a manually
  entered constant.

## Reporting

For each deterministic check, record the measured value, required value, units,
entities involved, method, and pass state. Link each visual finding to its room
or task view. A scene cannot pass while required room views, opening checks, or
task-relevant open-state evidence are missing.
