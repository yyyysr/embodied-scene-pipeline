# Offline validation and evidence

Reopen the final candidate USD and check its authored representation before
publication, using host OpenUSD and configuration schemas.

## Common checks

- Finite parameters, supported fields, material references and numeric bounds.
- Meter/Z-up units, unit-scale roots and disjoint physics ownership.
- Source connectivity, nondegeneracy and consistent edge orientation; closed edges
  for volume sources.
- Explicit API tokens and property types, effective physics materials and scene owner.
- Source bind poses, contact parameters and guide visibility.
- Resolved resources and preserved delivery hierarchy.

## Representation-specific checks

Volume checks verify automatic-generation APIs, enabled state, source relationship,
resolution policy and TetMesh declarations. Empty generated arrays are the expected
deferred representation; source geometry is checked at this stage.

Surface checks verify actual points, triangle indices, source-frame transforms,
current/rest agreement, velocities and bind poses. Attachment selections, targets
and local anchor positions are checked against that known topology.

These checks establish the authoring contract. Platform generation, appearance and
dynamics have separate evidence.

## Report and feedback

Keep one `review/report.json`. Its `usd.isaacsim` section records the target
profile, offline result, aggregate counts and volume generation state (`deferred`
or `not_required`). Dynamic evidence retains its own status.

Useful feedback identifies the asset and behavior: generated mesh quality, settling,
compression/rebound, sag, pin drift or contact penetration. Apply accepted corrections
to source/specifications and rebuild. Re-export marks earlier dynamic evidence for
re-acceptance in the same report.
