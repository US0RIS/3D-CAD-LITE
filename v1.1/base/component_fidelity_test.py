from __future__ import annotations

"""Release gate for purchased-component CAD fidelity.

This test exists specifically to prevent regressions where a component advertises
high-fidelity/manufacturer geometry but the desktop build silently renders a boxy
proxy instead.
"""

from pathlib import Path

import component_registry as registry
import physical_components


def fail(message: str) -> None:
    raise SystemExit(message)


def validate_component(cid: str, *, min_x: float, min_y: float, min_z: float,
                       min_solids: int, expected_fidelity: set[str]) -> None:
    c = registry.component_by_id(cid)
    fidelity = c.get("geometry", {}).get("fidelity")
    if fidelity not in expected_fidelity:
        fail(f"{cid}: unexpected geometry fidelity {fidelity!r}")

    assets = [a for a in c.get("geometry", {}).get("assets", []) if a.get("role") == "geometry"]
    if not assets:
        fail(f"{cid}: high-fidelity component has no geometry asset")
    path = registry.resolve_asset_path(assets[0])
    if path is None or not Path(path).is_file():
        fail(f"{cid}: bundled geometry asset does not resolve: {assets[0]}")

    obj = registry.make_project_object(cid)
    parts = physical_components.component_parts(obj)
    if not parts:
        fail(f"{cid}: geometry engine returned no parts")
    shape = physical_components.component_shape(obj)
    if shape is None:
        fail(f"{cid}: geometry engine returned no compound")

    bb = shape.BoundingBox()
    if bb.xlen < min_x or bb.ylen < min_y or bb.zlen < min_z:
        fail(
            f"{cid}: implausible CAD envelope {bb.xlen:.2f} x {bb.ylen:.2f} x {bb.zlen:.2f} mm"
        )
    try:
        solids = len(shape.Solids())
    except Exception:
        solids = 1
    if solids < min_solids:
        fail(f"{cid}: CAD contains only {solids} solids; expected at least {min_solids}")

    # Mounting datum must match the Raspberry Pi 58 x 49 mm M2.5 pattern.
    mount = registry.interface_by_id(c, "mount")
    meta = mount.get("metadata", {})
    if meta.get("pattern_mm") != [58, 49] or float(meta.get("hole_diameter_mm", 0)) != 2.7:
        fail(f"{cid}: incorrect Raspberry Pi mounting metadata: {meta}")


validate_component(
    "compute.raspberry_pi_4_model_b_8gb",
    min_x=84.0, min_y=55.0, min_z=14.0,
    min_solids=25,
    expected_fidelity={"detailed_parametric", "verified_step", "official_step"},
)
validate_component(
    "compute.raspberry_pi_5_8gb",
    min_x=84.0, min_y=55.0, min_z=12.0,
    min_solids=20,
    expected_fidelity={"official_step"},
)

# Search must expose both real boards rather than only generic compute envelopes.
search = registry.search_components("raspberry pi", category="compute", limit=20)
ids = {x.get("id") for x in search.get("results", [])}
for required in {"compute.raspberry_pi_4_model_b_8gb", "compute.raspberry_pi_5_8gb"}:
    if required not in ids:
        fail(f"component search does not expose {required}")

print("ForgeCAD component fidelity gate: PASS")
