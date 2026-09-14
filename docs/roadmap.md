# Roadmap

## Milestone 1 — minimal loop

- [x] Repository and agent scaffolding
- [x] Task and scene specifications
- [x] Tabletop example
- [x] Blender scene construction baseline
- [x] Diagnostic cameras, lighting, render, and report
- [ ] Run the example in a local Blender installation
- [ ] Iterate on checks from real rendered evidence

## Milestone 2 — spatial structure

- [ ] Irregular polygon room builder
- [ ] Wall openings and adjacency validation
- [ ] Isolated Structure and Room Agent outputs
- [ ] Multi-room integration example

## Milestone 3 — asset routing

- [x] Add optional tabletop background and clean-plate decision gates
- [x] Add FAL clean-plate adapters for Nano Banana and GPT Image 2 aliases
- [x] Add resumable World Labs generation with local SPZ outputs
- [x] Record accepted backgrounds without a background-specific manifest
- [x] Add resumable Hunyuan3D text and generated-reference asset routes
- [ ] Add asset normalization and quality checks
- [ ] Add direct SPZ visual review and explicit-asset alignment

## Milestone 4 — simulation semantics

- [x] Add separate USD authoring package
- [x] Define physics specification schema
- [x] Author bodies, colliders, joints, mass, friction, and joint drive damping
- [ ] User validates exported scenes in Isaac Sim
