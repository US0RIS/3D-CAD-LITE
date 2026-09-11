from __future__ import annotations

"""Release gate for purchased-component CAD fidelity.

This test prevents a repeat of the failure where a component claimed real-world
identity but the viewport silently rendered a generic gray proxy. It checks both
engineering-authority geometry and the component-specific visual representation.
"""

from pathlib import Path

import component_registry as registry
import physical_components


def fail(message: str) -> None:
    raise SystemExit(message)


def validate_component(cid: str, *, min_x: float, min_y: float, min_z: float,
                       min_solids: int, min_visual_parts: int, min_visual_colors: int,
                       expected_fidelity: set[str]) -> None:
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

    # Visual representation: this is what the user actually sees. It must be a
    # recognisable multi-part board, not one monochrome box/compound.
    parts = physical_components.component_parts(obj)
    if not parts:
        fail(f"{cid}: visual geometry engine returned no parts")
    if len(parts) < min_visual_parts:
        fail(f"{cid}: visual model contains only {len(parts)} part groups; expected >= {min_visual_parts}")
    colors = {str(color).lower() for _, color in parts}
    if len(colors) < min_visual_colors:
        fail(f"{cid}: visual model contains only {len(colors)} colors; expected >= {min_visual_colors}")

    # Engineering representation: exact/validated STEP takes priority when present.
    shape = physical_components.component_shape(obj)
    if shape is None:
        fail(f"{cid}: engineering geometry engine returned no shape")
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
    centers = meta.get("hole_centers_mm")
    expected_centers = [[-39, -24.5], [-39, 24.5], [19, -24.5], [19, 24.5]]
    if centers != expected_centers:
        fail(f"{cid}: incorrect Raspberry Pi mounting hole centers: {centers}")


validate_component(
    "compute.raspberry_pi_4_model_b_8gb",
    min_x=84.0, min_y=55.0, min_z=14.0,
    min_solids=25,
    min_visual_parts=10,
    min_visual_colors=5,
    expected_fidelity={"detailed_parametric", "verified_step", "official_step"},
)
validate_component(
    "compute.raspberry_pi_5_8gb",
    min_x=84.0, min_y=55.0, min_z=12.0,
    min_solids=20,
    min_visual_parts=10,
    min_visual_colors=5,
    expected_fidelity={"official_step"},
)

# Search must expose both real boards rather than only generic compute envelopes.
search = registry.search_components("raspberry pi", category="compute", limit=20)
ids = {x.get("id") for x in search.get("results", [])}
for required in {"compute.raspberry_pi_4_model_b_8gb", "compute.raspberry_pi_5_8gb"}:
    if required not in ids:
        fail(f"component search does not expose {required}")

# A specific purchased part must never claim official STEP without an actual STEP asset.
for c in registry.all_components():
    geometry = c.get("geometry", {})
    if geometry.get("fidelity") == "official_step":
        real_assets = [a for a in geometry.get("assets", []) if a.get("role") == "geometry" and a.get("format") in {"step", "stp"}]
        if not real_assets:
            fail(f"{c['id']}: claims official_step fidelity without a registered STEP asset")

print("ForgeCAD component fidelity gate: PASS")
