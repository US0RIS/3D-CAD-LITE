# ForgeCAD

ForgeCAD is a local-first, AI-native CAD/CAE engineering workbench built from the original **3D-CAD-LITE / WebCAD** prototype in this repository.

The original prototype treated Three.js scene meshes as the product. ForgeCAD reverses that architecture: **the engineering model is authoritative data**. The viewport is a client of that model, and AI agents use the same typed operations as the human UI.

The goal is not to reimplement OpenCascade, finite-element mathematics, or every commercial solver. The goal is to provide a coherent engineering IDE that makes mature kernels and numerical tools easy for humans and agents to manipulate, test, challenge, version, and eventually manufacture.

## Run

### macOS

Double-click `start.command`, or:

```bash
./start.command
```

### Windows

Double-click `start.bat`.

Python 3.11 or 3.12 is recommended for the smoothest CadQuery/OpenCascade installation.

Then open:

```text
http://127.0.0.1:8765
```

API documentation is available at `/docs`; the machine-readable contract is `/openapi.json`.

## What is implemented

### CAD kernel and geometry

- CadQuery + OpenCascade exact B-rep solids
- box, cylinder, sphere primitives
- sketch-profile extrusion:
  - rectangle
  - circle
  - arbitrary polygon
- revolved polygon profiles
- imported STEP solids
- through holes on X/Y/Z axes
- circular and rectangular pockets
- all-edge fillets and chamfers
- exact volume, surface area, centroid, bounding dimensions, and material-linked mass
- browser tessellation generated from the exact B-rep
- STEP and STL export
- move / rotate / scale viewport gizmo and numeric transforms
- millimeter-native, Z-up mechanical coordinate system

### Canonical engineering model

Projects persist more than geometry. They contain:

- parts and features
- materials and physical properties
- semantic roles and interfaces
- assembly joints
- loads and constraints
- measurable requirements
- purchased-component BOM and cost
- simulation provenance
- engineering notebook entries
- design history / ledger
- persistent design branches

A model entity has a stable UUID and semantic metadata, so an agent can reason about a `motor_mount`, `bearing_housing`, or `structural_base` rather than trying to locate “Face23” on screen.

### Assembly / dynamics

Assembly entities currently support:

- fixed joints
- revolute joints
- prismatic joints
- spherical joints
- spring metadata
- anchors, axes, limits, motor metadata, and rest state

The browser simulation sandbox uses Rapier in **SI units** and applies fixed/revolute/prismatic/spherical joints. Simulation pose is intentionally temporary: pressing Stop restores the canonical CAD transforms.

### Engineering materials

The built-in material library contains density, Young's modulus, yield strength, Poisson ratio, thermal conductivity, specific heat, emissivity, and display color for common:

- aluminum alloys
- steels
- Ti-6Al-4V
- ABS
- PETG
- PA12

The material model is intentionally plain JSON so future material sources can be imported without changing the CAD kernel.

### Structural analysis

Two levels are intentionally kept separate:

1. **Cantilever screening** — a fast analytical bounding-section beam model.
2. **Preview linear static FEA** — voxelization of the exact B-rep followed by five-tetrahedra-per-cell meshing, 3D isotropic elastic stiffness assembly, sparse solve, displacement recovery, von Mises stress recovery, and yield factor of safety.

FEA returns field samples to the browser, where they can be visualized directly over the selected part.

The preview solver is useful for early design iteration and convergence experiments. It is **not** presented as certification-grade analysis.

### Modal analysis

ForgeCAD includes preview eigenvalue analysis using:

- the tetrahedral structural mesh
- a full stiffness matrix
- lumped nodal mass
- generalized sparse eigenvalue solution
- fixed-face support conditions

It reports natural frequencies and records them in the project's simulation history so requirements such as `first_mode_hz >= 250` can be evaluated.

### Thermal analysis

The built-in thermal preview solver performs steady-state 3D conduction/convection analysis:

- exact B-rep voxelization
- volumetric heat distribution
- material thermal conductivity
- inter-cell conduction
- exposed-surface convection
- ambient temperature
- optional fixed-temperature face
- sparse steady-state solve
- temperature-field visualization

It does not silently model radiation, contact resistance, internal airflow, phase change, or temperature-dependent material behavior.

### Parameter optimization

The Design workspace can run bounded parameter optimization over numeric dimensions. The current optimizer uses differential evolution with:

- mass or volume objective
- user-selected variable bounds
- maximum deflection constraint
- minimum yield factor-of-safety constraint
- fast analytical screening during search

The candidate is not applied automatically. The user can inspect it, apply it explicitly, then rerun FEA.

### Manufacturing screening

Part-level process screening currently includes heuristics for:

- FDM
- SLA
- SLS
- CNC machining
- laser cutting

This layer is deliberately called screening. It reports likely process risks; it does not pretend to replace a machinist, print-process simulation, or supplier quote.

### Requirements as engineering tests

Requirements can target project or latest-analysis metrics, including:

- `mass_kg`
- `cost_usd`
- `parts`
- `volume_mm3`
- `max_displacement_mm`
- `yield_fos`
- `max_temperature_c`
- `first_mode_hz`

The model browser displays PASS / FAIL / unknown. Analysis results are stored with provenance, so a requirement only gets a numeric result after a corresponding analysis actually ran.

### Engineering notebook and provenance

Notebook entries can be categorized as:

- note
- decision
- experiment
- calculation

Every mutation records actor, action, reason, and time. Agent-generated modifications therefore remain auditable and undoable.

### Persistent branches

ForgeCAD includes local Git-like design branches. Branches persist as complete project snapshots and can be:

- created
- switched
- compared

Comparison identifies added, removed, and changed parts plus requirement and BOM deltas. This is intended for mechanical architecture exploration rather than source-code version control.

### AI / agent system

ForgeCAD detects local Ollama and exposes four engineering roles:

- **Designer** — emits allow-listed engineering commands and can execute them
- **Analyst** — recommends analyses, boundary conditions, and high-information experiments
- **Verifier** — independently tries to invalidate design/simulation conclusions
- **Optimizer** — proposes variables, bounds, objectives, constraints, and verification sequence

There is also a one-click **Designer → independent verifier** workflow.

The Designer cannot execute arbitrary Python or shell commands through the CAD command interface. It can only call deterministic engineering operations such as:

```json
{
  "op": "add_feature",
  "args": {
    "id": "existing-part-uuid",
    "feature": {
      "type": "hole",
      "diameter": 5,
      "x": 20,
      "y": 12,
      "z": 0,
      "axis": "z"
    }
  }
}
```

All operations are logged and undoable.

### External agents

The application is intentionally easy to drive without GUI automation:

- `GET /api/tools`
- `POST /api/command`
- `GET /openapi.json`
- `/docs`

A cloud reasoning model, local Ollama model, script, test harness, or future MCP/plugin wrapper can all manipulate the same canonical design model.

### Hardware / solver capability detection

The System dock reports:

- CPU architecture and thread count
- RAM when detectable
- built-in analysis capability
- Ollama status / local models
- availability of external engineering executables such as Gmsh, CalculiX, Elmer, OpenFOAM, and Code_Aster

This is the basis for choosing local solver fidelity based on the machine actually running ForgeCAD rather than assuming one generic workstation configuration.

## Trust model

ForgeCAD does not equate “the solver returned a number” with “the design is proven.”

Built-in analysis results carry explicit limitations. The independent verifier is prompted to examine:

- boundary conditions
- wrong load cases
- mesh convergence
- material assumptions
- contact / preload omissions
- thermal coupling
- fatigue
- manufacturing variation
- tolerances
- unsupported requirement claims

For safety-critical, expensive, fatigue-sensitive, nonlinear-contact, fluid, electromagnetic, or certification decisions, use a validated external solver and physical testing.

## Architecture

See [`ARCHITECTURE.md`](ARCHITECTURE.md).

Core files:

- `core.py` — canonical project model, exact geometry, semantic entities, history, branches, commands
- `analysis.py` — structural, modal, thermal, optimization, manufacturing, hardware capability detection
- `agents.py` — Ollama command planning and independent engineering roles
- `server.py` — FastAPI engineering API and file import/export
- `static/index.html` — application shell
- `static/app.js` — viewport, analysis visualization, simulation, inspectors, agent UI
- `static/styles.css` — UI design system
- `smoke_test.py` — end-to-end backend regression tests
- `legacy/WebCAD_v0.3.9.html` — preserved original prototype

## Tests

Run:

```bash
python smoke_test.py
```

The regression suite covers exact geometry, feature subtraction, tessellation, history, joints, loads, constraints, requirements, FEA, modal analysis, thermal analysis, optimization, BOM cost, notebook, persistent branches, STEP import/export, capability discovery, and the OpenAPI/tool contract.

## Current boundary of the product

ForgeCAD is now a real integrated engineering workbench, but it is not a drop-in replacement for every specialist solver in Ansys/COMSOL/OpenFOAM. The built-in solvers deliberately target fast local design iteration. The architecture reserves external-solver integrations for the cases where solver maturity matters more than interactivity.

The largest remaining specialist layers are:

- fully constrained general-purpose 2D sketch solving
- persistent named B-rep topology across arbitrary feature-history edits
- high-order / unstructured validated meshing
- nonlinear/contact/fatigue FEA through established external solvers
- full CFD
- electromagnetics
- coupled multiphysics
- production drawings/GD&T and machining toolpath generation

Those are intentionally separate from the canonical model and agent API, so adding them does not require rewriting the application.
