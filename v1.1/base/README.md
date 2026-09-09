# ForgeCAD v1

ForgeCAD is a local-first, AI-native mechanical/electromechanical engineering workbench. It is designed around one canonical project model: the 3D UI, local Qwen engineering agent, embedded-code editor, analysis tools, and Jarvis integration all operate through the same deterministic typed commands instead of UI automation.

## v1 release scope

- Exact CadQuery B-rep primitives, STEP import, STEP/STL export, features, transforms, tessellation, materials and physical metrics.
- Design branches/tabs with persistent history, comparisons, `working` / `working_in_real_life` status, and protection of physically verified baselines. A mutation of a protected design automatically occurs on a child experiment branch.
- A 238-item offline real-component registry covering Raspberry Pi/MCU compute, solenoids, stepper motors, servos, bearings, metric fasteners, linear rails, fans, batteries, sensors and power electronics. Search/selection is deterministic and constraint-aware.
- Programmable real components carry a versioned code workspace. The embedded Code dock reads, writes and validates those files without leaving ForgeCAD; agent operations can write the same workspace.
- Built-in fast structural, modal and thermal screening, parameter optimization and manufacturing checks. These are explicitly screening-grade, not certification solvers.
- Local Ollama integration, pinned by default to `qwen3:8b`.
- Loopback-only Jarvis bridge with a per-install token and branch-before-remote-mutation behavior.
- Native desktop shells for macOS and Windows via pywebview.

## Architecture

Core files:

- `core.py` — canonical project state, exact geometry, history, design branches, typed commands.
- `components.py` — offline real-world component catalog and deterministic selection.
- `software.py` — embedded device code workspaces and validation.
- `analysis.py` — transparent design-iteration analysis and optimization.
- `agents.py` — local Ollama planning/review/chat.
- `jarvis_bridge.py` — loopback discovery/token boundary.
- `server.py` — FastAPI application protocol shared by UI/AI/Jarvis.
- `desktop.py` — macOS/Windows desktop host and local engine.
- `static/` — premium 3D UI, design tabs, component browser, analysis and code docks.

## Trust boundary

ForgeCAD deliberately distinguishes exact geometry from screening analysis and physical verification. Structural/modal/thermal previews are intended to catch design issues and compare variants quickly. Safety-critical, fatigue-sensitive, nonlinear/contact, fluid, regulatory or expensive decisions require an appropriately validated solver workflow and physical testing.

## Source development

```bash
python -m pip install -r requirements.txt
python prepare_frontend.py
python smoke_test.py
python v1_test.py
python server.py
```

Open `http://127.0.0.1:8765`.

## Windows release

Run `windows/build.ps1`. It builds a self-contained `ForgeCAD` application folder and an Inno Setup installer:

- `dist/ForgeCAD-Windows-x64.zip`
- `dist/installer/ForgeCAD-Setup.exe`

## macOS release

Run `macos/build.sh` on Apple Silicon macOS. It creates an ad-hoc-signed `.app` and DMG:

- `dist/ForgeCAD-v1-macOS-arm64.dmg`
- `dist/ForgeCAD-v1-macOS-arm64-app.zip`

Because this release is not Apple-notarized, first launch may require Control-click → Open.
