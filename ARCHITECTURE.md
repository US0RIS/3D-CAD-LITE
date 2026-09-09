# ForgeCAD architecture

## Product thesis

ForgeCAD is an **engineering IDE**, not a GUI wrapper around a mesh viewer.

```text
Human engineer ───────────────┐
                              │
Local / cloud AI agent ───────┼──► Typed Engineering API
                              │              │
Automated test / optimizer ───┘              ▼
                                      Canonical Design IR
                                ┌─────────────┼─────────────┐
                                ▼             ▼             ▼
                           Geometry        Analysis      Provenance
                         CadQuery/OCCT    local/remote   ledger/branch
                                │             │
                                ▼             ▼
                             B-rep       solver results
                                │             │
                                └──────► Three.js view
```

The viewport has no privileged mutation path. Anything a person does through the inspector becomes the same deterministic model command an agent would issue.

## Canonical design intermediate representation

The project JSON is the common language between:

- CAD
- simulation
- agents
- UI
- optimization
- requirements
- manufacturing
- versioning

Important entity types are:

```text
Project
├── Parts
│   ├── Parameters
│   ├── Feature history
│   ├── Transform
│   ├── Material
│   ├── Physical properties
│   ├── Semantic role / interfaces
│   └── Manufacturing intent
├── Joints
├── Loads
├── Constraints
├── Requirements
├── BOM
├── Simulations
├── Notebook
├── Engineering ledger
└── Branch metadata
```

IDs are stable UUIDs. Human-readable names are not used as foreign keys.

## Semantic identity

Conventional CAD frequently exposes topological names such as Face23 that are brittle after model regeneration. ForgeCAD adds semantic identity at the product-model level:

```json
{
  "semantic": {
    "role": "motor_mount",
    "tags": ["left_shoulder", "machined"],
    "interfaces": []
  }
}
```

Loads and constraints currently reference stable part IDs plus canonical face selectors such as `x-min` and `z-max`. Future named-topology work can replace those selectors without changing the command protocol.

## Geometry

`core.build_shape()` converts the IR into an exact OpenCascade B-rep through CadQuery. Three.js never becomes authoritative geometry.

Current procedural roots:

- box
- cylinder
- sphere
- profile extrude
- profile revolve
- STEP import

Current secondary features:

- through hole
- circular pocket
- rectangular pocket
- all-edge fillet
- all-edge chamfer

The browser asks the backend for tessellation. STEP/STL export uses the same exact shape.

## Solver tiers

### Tier 0 — analytical screening

Cheap closed-form calculations intended to catch impossible concepts and provide parameter-optimization speed.

### Tier 1 — built-in local preview solvers

Implemented for interactivity and transparency:

- linear static elasticity
- modal eigenanalysis
- steady-state heat conduction/convection

These operate on voxel/tetra or voxel/control-volume discretizations derived from the B-rep.

### Tier 2 — established external solvers

The system capability layer already detects common solver executables. The canonical model is intentionally solver-neutral so adapters can translate the same loads, materials, constraints, and geometry into:

- CalculiX / Code_Aster for structural analysis
- Elmer for multiphysics
- OpenFOAM for CFD
- Gmsh for meshing
- other commercial or remote solvers

Tier 2 results should be stored in the same simulation history and requirement-checking pipeline.

### Tier 3 — physical validation

No numerical stack removes the need for experimental validation when real-world uncertainty dominates. Notebook entries are designed to carry experiment evidence back into the digital project.

## Simulation sandbox

Rigid-body dynamics is intentionally separated from authoritative CAD state.

```text
CAD transform ──► create Rapier body ──► simulate temporary pose
      ▲                                      │
      └──────────── Stop / restore ──────────┘
```

This prevents “I dropped the assembly” from becoming an accidental design edit.

## Requirements as tests

A requirement is a machine-readable assertion:

```json
{
  "metric": "yield_fos",
  "operator": ">=",
  "value": 2.0
}
```

Geometry-only metrics can be evaluated immediately. Analysis metrics remain unknown until a corresponding simulation has actually run. This prevents agents from converting an untested design into a green dashboard by assumption.

## Independent verification

The verifier role receives canonical project state and recent simulations but does not inherit the Designer's reasoning transcript. Its job is adversarial technical review:

- invalidate boundary conditions
- detect wrong load cases
- demand convergence evidence
- identify missing contact/preload
- question temperature-dependent material assumptions
- identify fatigue/manufacturing/tolerance risks
- detect unsupported requirement conclusions

That separation is deliberate; the agent that created a design should not be the only agent judging it.

## Branches

ForgeCAD branches are design-state snapshots, not Git refs. This is useful because design alternatives should include geometry, requirements, simulations, BOM, and decisions as one object.

A future Git bridge can persist branch snapshots into source control, but the mechanical design abstraction does not depend on Git being installed.

## Local-first operation

The Python CAD/analysis stack and project data run locally. Ollama is optional. Cloud agents can use the HTTP contract without becoming the data model.

The browser currently loads pinned Three.js and Rapier JavaScript modules from public package CDNs. They are renderer/dynamics clients rather than design data dependencies. A native/packaged distribution can vendor those modules without changing any engineering code.
