# Deformable asset contract

Use a semantic Xform root with a meter-scale orthonormal world transform. Register
one source mesh below it with `context.register_reference`. Each deformable owns
its hierarchy separately from rigid bodies and visual-only context.

```text
soft_object                 Xform: deformable owner, physics material binding
  source/render mesh        Mesh: appearance, source geometry and bind pose
  SimulationMesh            TetMesh declaration (volume) or triangle Mesh (surface)
  CollisionMesh             TetMesh declaration for volume hex generation
```

SimulationMesh and CollisionMesh are reserved names and use guide purpose.
Attachment targets live outside the deformable hierarchy.

## Volume geometry

Provide a closed, consistently oriented, nondegenerate triangle source. The root
declares `OmniPhysicsDeformableBodyAPI`, `PhysxAutoDeformableBodyAPI` and the
`physxDeformableBody:cookingSourceMesh` relationship. Automatic generation is enabled.
SimulationMesh declares `OmniPhysicsVolumeDeformableSimAPI`.

With `cooking.volume_hex_resolution`, declare `PhysxAutoDeformableHexahedralMeshAPI`,
its resolution and a separate collision TetMesh. Otherwise the simulation TetMesh
also carries collision. These nodes contain no generated arrays at delivery:
the platform fills them from the source and parameters before simulation.
Choose resolution for the smallest relevant contact region.

Set physical dimensions before density or mass. A closed outer envelope describes
a filled volume; a hollow elastic object needs geometry representing its material
volume if that distinction matters to the task.

## Surface geometry

The source triangle topology becomes an explicit simulation Mesh in the root frame.
That mesh also carries collision, current/rest points, rest triangle indices and
initial velocities. Choose `rest_bend: flatDefault` for a flat rest policy or
`restShapeDefault` for authored rest curvature.

## Rest, initial and bind state

`rest_shape: source` declares the authored shape as the unloaded initial shape.
Volume bodies start at rest; surfaces may specify uniform initial velocity.

Each authored render mesh carries `OmniPhysicsDeformablePoseAPI:default`,
bind-purpose and bind points. Generated volume meshes carry bind-purpose declarations,
whose point arrays are populated with generation. Explicit surface meshes carry
their bind points at delivery.

The supported construction represents elastic volume/surface bodies with one material
per body. Prestress, plasticity, tearing, sewing and fluids require other models.

## Mass and materials

Bind mechanical materials with the `physics` purpose independently of appearance.
Provide density or explicit mass; explicit mass takes precedence. Estimate volume
mass from enclosed volume × density, and surface mass from area × thickness × density.

## Attachments

Explicit node-to-Xform attachments use surface meshes, whose nodes exist at build
time. Select nodes with a body-local axis-aligned box, transform initial positions
into the target frame, and write the arrays into USD. Empty selections fail.
Volume node attachments require generated topology and are outside this contract.
Describe permanent pins or idealized holds separately from frictional grasps.
