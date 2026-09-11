from __future__ import annotations

"""Geometry, mating, and reality checks for ForgeCAD purchased components.

A component in ForgeCAD is not a decorative proxy. The geometry layer prefers
registered STEP assets and only falls back to explicit, fidelity-labelled
parametric models. Generic category envelopes remain available for low-fidelity
catalog entries, but they are never silently treated as manufacturer CAD.
"""

import math
from copy import deepcopy
from typing import Any, Callable

import cadquery as cq
import component_registry as registry


def _box(x: float, y: float, z: float, color: str = "#888888",
         center=(0, 0, 0), radius: float = 0.0):
    cx, cy, cz = center
    wp = cq.Workplane("XY").workplane(offset=cz - z / 2).box(
        x, y, z, centered=(True, True, False)
    )
    if radius > 0:
        try:
            wp = wp.edges("|Z").fillet(min(radius, x / 2 - 0.01, y / 2 - 0.01))
        except Exception:
            pass
    return wp.val().translate((cx, cy, 0)), color


def _cyl(d: float, h: float, color: str = "#888888",
         center=(0, 0, 0), axis="z"):
    cx, cy, cz = center
    half = float(h) / 2.0
    if axis == "x":
        sh = cq.Workplane("YZ").circle(d / 2).extrude(half, both=True).val().translate((cx, cy, cz))
    elif axis == "y":
        sh = cq.Workplane("XZ").circle(d / 2).extrude(half, both=True).val().translate((cx, cy, cz))
    else:
        sh = cq.Workplane("XY").circle(d / 2).extrude(half, both=True).val().translate((cx, cy, cz))
    return sh, color


def _cut_holes(shape, points, diameter, depth, offset_z):
    out = shape
    for x, y in points:
        cutter = (
            cq.Workplane("XY").workplane(offset=offset_z)
            .center(x, y).circle(diameter / 2).extrude(depth).val()
        )
        out = out.cut(cutter)
    return out


def _pi_gpio(parts, center_x=-10.0, center_y=24.2):
    parts.append(_box(51.0, 5.1, 2.5, "#17191b", (center_x, center_y, 2.05), 0.3))
    pins = []
    x0 = center_x - 24.13
    for col in range(20):
        for row in range(2):
            pins.append(
                _box(
                    0.64, 0.64, 8.5, "#d7a928",
                    (x0 + col * 2.54, center_y - 1.27 + row * 2.54, 5.3),
                    0.06,
                )[0]
            )
    parts.append((cq.Compound.makeCompound(pins), "#d7a928"))


def _pi4_parts():
    """Detailed Pi 4 Model B fallback derived from Raspberry Pi mechanical data."""
    parts = []
    board, _ = _box(85, 56, 1.6, "#16813e", radius=3)
    board = _cut_holes(
        board,
        [(-39, -24.5), (-39, 24.5), (19, -24.5), (19, 24.5)],
        2.7, 3, -1.5,
    )
    parts.append((board, "#16813e"))
    _pi_gpio(parts)

    # Major silicon and RF/package areas.
    for args in [
        (15.5, 15.5, 2.2, "#202327", (-5.5, -1.0, 1.9)),
        (12.5, 10.5, 1.5, "#25282b", (12.0, -1.0, 1.55)),
        (9.0, 9.0, 1.4, "#2b2e32", (19.5, 11.0, 1.5)),
        (14.5, 12.5, 1.4, "#25282b", (-27.0, 11.5, 1.5)),
        (15.0, 12.5, 2.0, "#c4c8ca", (-31.5, 18.0, 1.8)),
    ]:
        parts.append(_box(*args))

    # Right-edge I/O shells: Ethernet, USB 3 and USB 2.
    for args in [
        (21.0, 16.2, 13.5, "#aeb5bc", (37.0, 17.75, 7.55)),
        (17.2, 14.8, 16.0, "#aab2ba", (38.4, -1.0, 8.8)),
        (17.2, 14.8, 16.0, "#aab2ba", (38.4, -19.0, 8.8)),
    ]:
        parts.append(_box(*args))

    # Bottom-edge I/O.
    for args in [
        (9.0, 7.6, 3.2, "#b9bec4", (-33.0, -29.0, 2.4)),
        (7.6, 7.2, 3.0, "#b8bdc3", (-17.8, -29.0, 2.3)),
        (7.6, 7.2, 3.0, "#b8bdc3", (-4.3, -29.0, 2.3)),
        (10.4, 9.2, 5.5, "#9da5ac", (11.7, -27.7, 3.15)),
        (17.0, 3.6, 3.1, "#e2ded4", (5.0, 4.5, 2.35)),
        (17.0, 3.6, 3.1, "#e2ded4", (-31.0, 4.0, 2.35)),
        (15.0, 13.0, 1.7, "#9da5ac", (-34.5, 4.0, -1.65)),
    ]:
        parts.append(_box(*args))
    parts.append(_cyl(6.2, 12.0, "#202225", (11.7, -30.2, 3.0), "y"))

    # Representative passive banks.
    passives = []
    for i in range(7):
        passives.append(_box(2.0, 1.0, 1.1, "#c9c2ad", (-24 + i * 3.2, -10.5, 1.35), 0.12)[0])
    for i in range(6):
        passives.append(_box(1.8, 0.9, 1.0, "#b8b1a0", (7.5 + i * 2.8, 16.0, 1.3), 0.1)[0])
    parts.append((cq.Compound.makeCompound(passives), "#c9c2ad"))
    return parts


def _pi5_parts():
    """Detailed Pi 5 fallback used only if the bundled official STEP is unavailable."""
    parts = []
    board, _ = _box(85, 56, 1.6, "#16813e", radius=3)
    board = _cut_holes(
        board,
        [(-39, -24.5), (-39, 24.5), (19, -24.5), (19, 24.5)],
        2.7, 3, -1.5,
    )
    parts.append((board, "#16813e"))
    _pi_gpio(parts)

    for args in [
        (17.2, 17.2, 1.7, "#202327", (-8, -1, 1.65)),
        (12.5, 12.5, 1.4, "#24272b", (11, 2, 1.5)),
        (7, 7, 1.2, "#2a2d31", (-20, 11, 1.4)),
        (8, 6, 1.1, "#303338", (19, -12, 1.35)),
        (19, 17, 13.5, "#aeb5bc", (42.5, -16.5, 7.55)),
        (17, 14, 15.2, "#aab2ba", (43.5, 3, 8.4)),
        (17, 14, 15.2, "#aab2ba", (43.5, 19, 8.4)),
        (9.2, 8, 3.4, "#b9bec4", (-31, -29.3, 2.5)),
        (7.6, 7.2, 3.2, "#b8bdc3", (-14, -29, 2.4)),
        (7.6, 7.2, 3.2, "#b8bdc3", (-2, -29, 2.4)),
        (15, 13, 1.7, "#9da5ac", (-35, 1, -1.65)),
        (17, 3.8, 3.1, "#e2ded4", (17.5, -23.5, 2.35)),
        (17, 3.8, 3.1, "#e2ded4", (17.5, 15.5, 2.35)),
        (11, 3.5, 2.8, "#e2ded4", (-30, 22, 2.2)),
        (6, 4, 3.3, "#eee9df", (25, 23, 2.45)),
        (4.5, 4.5, 2.8, "#d9dde0", (-39, 18, 2.2)),
    ]:
        parts.append(_box(*args))
    return parts


def _bearing_parts(c):
    s = c.get("specs", {})
    d = float(s.get("outer_diameter_mm") or c.get("dimensions_mm", [22])[0])
    b = float(s.get("bore_mm") or max(3, d * .35))
    w = float(s.get("width_mm") or c.get("dimensions_mm", [0, 0, 7])[2])
    outer = cq.Workplane("XY").circle(d / 2).circle(b / 2).extrude(w / 2, both=True).val()
    shield = cq.Workplane("XY").circle(d * .44).circle(b * .54).extrude(w * .41, both=True).val()
    return [(outer, "#aeb4ba"), (shield, "#6e747b")]


def _stepper_parts(c):
    x, y, z = [float(v) for v in c["dimensions_mm"]]
    face = min(x, y)
    body, _ = _box(x * .96, y * .96, z, "#25282c", radius=2)
    front, _ = _box(x, y, 3, "#9ba2a8", (0, 0, z / 2 - 1.5), 1.5)
    rear, _ = _box(x * .94, y * .94, 2, "#6f747a", (0, 0, -z / 2 + 1), 1)
    pilot = _cyl(max(16, face * .52), 2, "#aab0b5", (0, 0, z / 2 + 1))[0]
    shaft_d = 5 if face <= 42 else 6.35
    shaft = _cyl(shaft_d, 20, "#c4c9cd", (0, 0, z / 2 + 10))[0]
    spacing = {20: 15.4, 28: 23, 35: 26, 42: 31, 57: 47.14}.get(round(face), face * .73)
    pts = [(-spacing / 2, -spacing / 2), (spacing / 2, -spacing / 2),
           (spacing / 2, spacing / 2), (-spacing / 2, spacing / 2)]
    front = _cut_holes(front, pts, 3 if face <= 42 else 5, 5, z / 2 - 3)
    return [(body, "#25282c"), (front, "#9ba2a8"), (rear, "#6f747a"),
            (pilot, "#aab0b5"), (shaft, "#c4c9cd")]


def _servo_parts(c):
    x, y, z = [float(v) for v in c["dimensions_mm"]]
    body, _ = _box(x * .88, y, z * .82, "#2b2d30", (0, 0, -z * .04), 2)
    ear, _ = _box(x * 1.14, y * 1.05, z * .10, "#25272a", (0, 0, z * .22), 1)
    top = _cyl(min(x, y) * .42, z * .16, "#d0d3d6", (x * .20, 0, z * .46))[0]
    spline = _cyl(min(x, y) * .18, z * .10, "#d5d8da", (x * .20, 0, z * .59))[0]
    return [(body, "#2b2d30"), (ear, "#25272a"), (top, "#d0d3d6"), (spline, "#d5d8da")]


def _solenoid_parts(c):
    x, y, z = [float(v) for v in c["dimensions_mm"]]
    stroke = float(c.get("specs", {}).get("stroke_mm") or 10)
    body, _ = _box(x, y, max(10, z - stroke), "#303337", (0, 0, -stroke / 2), 2)
    cap, _ = _box(x * 1.05, y * 1.05, 3, "#9aa0a5", (0, 0, z / 2 - stroke - 1.5), 1)
    plunger = _cyl(min(x, y) * .24, stroke + 18, "#c4c8cb",
                   (0, 0, z / 2 - stroke / 2 + 6))[0]
    return [(body, "#303337"), (cap, "#9aa0a5"), (plunger, "#c4c8cb")]


def _fan_parts(c):
    x, y, z = [float(v) for v in c["dimensions_mm"]]
    frame, _ = _box(x, y, z, "#22262a", radius=max(1, x * .06))
    frame = frame.cut(cq.Workplane("XY").circle(min(x, y) * .39).extrude(z + 2, both=True).val())
    hole_space = min(x, y) * .82
    frame = _cut_holes(
        frame,
        [(-hole_space / 2, -hole_space / 2), (hole_space / 2, -hole_space / 2),
         (hole_space / 2, hole_space / 2), (-hole_space / 2, hole_space / 2)],
        max(2.5, x * .04), z + 4, -z,
    )
    hub = _cyl(min(x, y) * .24, z * .55, "#3a3e43")[0]
    blades = []
    for i in range(7):
        blade, _ = _box(min(x, y) * .30, min(x, y) * .07, z * .22,
                        "#34383d", (min(x, y) * .20, 0, 0), min(x, y) * .025)
        blades.append(blade.rotate((0, 0, 0), (0, 0, 1), i * 360 / 7 + 25))
    return [(frame, "#22262a"), (hub, "#3a3e43"),
            (cq.Compound.makeCompound(blades), "#34383d")]


def _fastener_parts(c):
    s = c.get("specs", {})
    d = float(s.get("diameter_mm") or c.get("legacy", {}).get("diameter_mm") or 3)
    length = float(s.get("length_mm") or c.get("legacy", {}).get("length_mm") or 12)
    head_d, head_h = d * 1.7, d
    shaft = _cyl(d, length, "#aeb4ba", (0, 0, -length / 2))[0]
    head = _cyl(head_d, head_h, "#8e959b", (0, 0, head_h / 2))[0]
    socket = cq.Workplane("XY").polygon(6, d * .62).extrude(head_h * .55).val().translate((0, 0, head_h * .58))
    return [(shaft, "#aeb4ba"), (head.cut(socket), "#8e959b")]


def _rail_parts(c):
    x, y, z = [float(v) for v in c["dimensions_mm"]]
    rail, _ = _box(x, max(3, y * .45), max(2, z * .34), "#a3a9ae", (0, 0, -z * .25), .5)
    carriage, _ = _box(min(50, max(20, y * 1.8)), y, z * .62, "#686e74", (0, 0, z * .08), 1)
    return [(rail, "#a3a9ae"), (carriage, "#686e74")]


def _pcb_parts(c):
    x, y, z = [float(v) for v in c["dimensions_mm"]]
    board_h = min(1.6, max(.8, z * .25))
    board, _ = _box(x, y, board_h, "#167a3b", radius=min(3, min(x, y) * .06))
    chip, _ = _box(min(16, x * .28), min(16, y * .35), max(1, min(2, z * .2)),
                   "#25282b", (0, 0, board_h / 2 + 1))
    header, _ = _box(min(x * .65, 35), min(5, y * .18), max(2, min(7, z * .6)),
                     "#17191b", (0, y * .38, max(1, z * .20)))
    conn, _ = _box(min(10, x * .22), min(9, y * .28), max(3, min(8, z * .7)),
                   "#b6bcc1", (x * .42, 0, max(1, z * .24)))
    return [(board, "#167a3b"), (chip, "#25282b"), (header, "#17191b"), (conn, "#b6bcc1")]


def _battery_parts(c):
    x, y, z = [float(v) for v in c["dimensions_mm"]]
    body, _ = _box(x, y, z, "#45484d", radius=min(4, min(x, y, z) * .12))
    lead1 = _cyl(1.2, min(15, x * .2), "#d43c35", (x / 2 + min(15, x * .2) / 2, 2, 0), "x")[0]
    lead2 = _cyl(1.2, min(15, x * .2), "#25282b", (x / 2 + min(15, x * .2) / 2, -2, 0), "x")[0]
    return [(body, "#45484d"), (lead1, "#d43c35"), (lead2, "#25282b")]


def _power_supply_parts(c):
    x, y, z = [float(v) for v in c["dimensions_mm"]]
    base, _ = _box(x, y, 1.2, "#aab0b4", (0, 0, -z / 2 + .6), 1)
    side1, _ = _box(x, 1.2, z, "#9ba1a6", (0, -y / 2 + .6, 0), .5)
    side2, _ = _box(x, 1.2, z, "#9ba1a6", (0, y / 2 - .6, 0), .5)
    end, _ = _box(1.2, y, z, "#9ba1a6", (-x / 2 + .6, 0, 0), .5)
    top, _ = _box(x * .72, y * .86, 1.0, "#b4b9bd", (x * .08, 0, z / 2 - .5), 1)
    terminal, _ = _box(12, min(55, y * .55), 12, "#303337", (x / 2 - 8, -y * .15, z / 2 - 6), 1)
    vents = []
    for i in range(8):
        vents.append(_box(x * .34, 2, .7, "#596066", (-x * .12, -y * .31 + i * y * .075, z / 2 + .15), .2)[0])
    return [(base, "#aab0b4"), (side1, "#9ba1a6"), (side2, "#9ba1a6"),
            (end, "#9ba1a6"), (top, "#b4b9bd"), (terminal, "#303337"),
            (cq.Compound.makeCompound(vents), "#596066")]


def _merge_live_asset_locations(snapshot: dict[str, Any], live: dict[str, Any]) -> dict[str, Any]:
    """Restore runtime-only asset locations stripped from immutable project snapshots."""
    out = deepcopy(snapshot)
    live_assets = live.get("geometry", {}).get("assets", [])
    by_key = {}
    for asset in live_assets:
        for key in (asset.get("id"), asset.get("filename")):
            if key:
                by_key[str(key)] = asset
    for asset in out.get("geometry", {}).get("assets", []):
        match = by_key.get(str(asset.get("id") or "")) or by_key.get(str(asset.get("filename") or ""))
        if not match:
            continue
        for key in ("path", "relative_path"):
            if match.get(key):
                asset[key] = match[key]
    return out


def component_definition(obj):
    snap = obj.get("component_snapshot")
    ref = obj.get("component_ref")
    if isinstance(snap, dict) and snap.get("id") == ref:
        try:
            return _merge_live_asset_locations(snap, registry.component_by_id(ref))
        except KeyError:
            return deepcopy(snap)
    if ref:
        try:
            return registry.component_by_id(ref)
        except KeyError:
            return None
    return None


def _step_asset(c):
    if not c:
        return None
    for asset in c.get("geometry", {}).get("assets", []):
        if asset.get("role") == "geometry" and asset.get("format") in {"step", "stp"}:
            path = registry.resolve_asset_path(asset)
            if path and path.is_file():
                return path
    return None


def _shape_matches_declared_envelope(shape, c) -> bool:
    try:
        bb = shape.BoundingBox()
        dims = [float(v) for v in c.get("dimensions_mm", [0, 0, 0])]
        if not all(v > 0 for v in dims):
            return True
        # STEP can extend beyond board dimensions because connectors overhang, so this is
        # deliberately permissive while still rejecting obviously corrupt/unit-scaled assets.
        return (
            bb.xlen >= dims[0] * .55 and bb.ylen >= dims[1] * .55 and bb.zlen >= min(1.0, dims[2] * .15)
            and bb.xlen <= dims[0] * 5 and bb.ylen <= dims[1] * 5 and bb.zlen <= max(dims[2] * 5, 50)
        )
    except Exception:
        return False


def component_parts(obj):
    c = component_definition(obj)
    if not c:
        return None
    profile = str(c.get("geometry", {}).get("profile") or c.get("category") or "box")

    # Visual geometry is deliberately component-specific and color-coded for boards.
    # Manufacturer STEP remains the engineering authority through component_shape().
    if profile == "raspberry_pi_4_model_b":
        return _pi4_parts()
    if profile == "raspberry_pi_5":
        return _pi5_parts()

    step = _step_asset(c)
    if step:
        try:
            shape = cq.importers.importStep(str(step)).val()
            if _shape_matches_declared_envelope(shape, c):
                return [(shape, "#aeb7c2")]
        except Exception:
            pass

    dispatch = {
        "bearing": _bearing_parts,
        "stepper_motor": _stepper_parts,
        "servo": _servo_parts,
        "solenoid": _solenoid_parts,
        "fan": _fan_parts,
        "fastener": _fastener_parts,
        "linear_motion": _rail_parts,
        "compute": _pcb_parts,
        "microcontroller": _pcb_parts,
        "sensor": _pcb_parts,
        "power": _pcb_parts,
        "battery": _battery_parts,
        "power_supply": _power_supply_parts,
    }
    fn = dispatch.get(profile) or dispatch.get(str(c.get("category")))
    if fn:
        try:
            return fn(c)
        except Exception:
            pass
    x, y, z = [float(v) for v in c.get("dimensions_mm", [20, 20, 20])]
    return [_box(x, y, z, "#727b84", radius=min(x, y, z) * .03)]


def component_shape(obj):
    """Return engineering-authority geometry for analysis/collision/export.

    If a validated STEP asset exists it wins, even when the viewport uses a richer
    color-coded parametric representation. This keeps visual usability separate
    from the mechanical authority used to decide whether something physically fits.
    """
    c = component_definition(obj)
    if c:
        step = _step_asset(c)
        if step:
            try:
                shape = cq.importers.importStep(str(step)).val()
                if _shape_matches_declared_envelope(shape, c):
                    return shape
            except Exception:
                pass
    parts = component_parts(obj)
    return cq.Compound.makeCompound([s for s, _ in parts]) if parts else None


def _norm(v):
    n = math.sqrt(sum(float(x) * float(x) for x in v))
    return [float(x) / n for x in v] if n > 1e-12 else [0, 0, 1]


def _dot(a, b):
    return sum(float(x) * float(y) for x, y in zip(a, b))


def _cross(a, b):
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def _mat_vec(m, v):
    return [sum(m[i][j] * v[j] for j in range(3)) for i in range(3)]


def _mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _rot_xyz(deg):
    x, y, z = [math.radians(float(v)) for v in deg]
    cx, sx = math.cos(x), math.sin(x)
    cy, sy = math.cos(y), math.sin(y)
    cz, sz = math.cos(z), math.sin(z)
    return _mat_mul(
        [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]],
        _mat_mul([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]],
                 [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]),
    )


def _align(a, b):
    a, b = _norm(a), _norm(b)
    v = _cross(a, b)
    c = max(-1, min(1, _dot(a, b)))
    s = math.sqrt(_dot(v, v))
    if s < 1e-10:
        if c > 0:
            return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        trial = [1, 0, 0] if abs(a[0]) < .9 else [0, 1, 0]
        v = _norm(_cross(a, trial))
        x, y, z = v
        return [[2 * x * x - 1, 2 * x * y, 2 * x * z],
                [2 * x * y, 2 * y * y - 1, 2 * y * z],
                [2 * x * z, 2 * y * z, 2 * z * z - 1]]
    x, y, z = [q / s for q in v]
    C = 1 - c
    return [
        [c + x * x * C, x * y * C - z * s, x * z * C + y * s],
        [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
        [z * x * C - y * s, z * y * C + x * s, c + z * z * C],
    ]


def _euler_xyz(m):
    y = math.asin(max(-1, min(1, -m[2][0])))
    if abs(math.cos(y)) > 1e-8:
        x, z = math.atan2(m[2][1], m[2][2]), math.atan2(m[1][0], m[0][0])
    else:
        x, z = math.atan2(-m[1][2], m[1][1]), 0
    return [math.degrees(x), math.degrees(y), math.degrees(z)]


def object_interface(obj, interface_id):
    for interface in obj.get("interfaces", []):
        if interface.get("id") == interface_id:
            return deepcopy(interface)
    c = component_definition(obj)
    if c:
        return registry.interface_by_id(c, interface_id)
    raise KeyError(interface_id)


def world_interface(obj, interface_id):
    interface = object_interface(obj, interface_id)
    transform = obj.get("transform", {})
    rotation = _rot_xyz(transform.get("rotation_deg", [0, 0, 0]))
    position = transform.get("position", [0, 0, 0])
    wp = _mat_vec(rotation, interface.get("position_mm", [0, 0, 0]))
    wa = _mat_vec(rotation, interface.get("axis", [0, 0, 1]))
    return {
        **interface,
        "world_position_mm": [wp[j] + float(position[j]) for j in range(3)],
        "world_axis": _norm(wa),
    }


def mate_objects(source, target, source_interface, target_interface, gap_mm=0.0):
    si = object_interface(source, source_interface)
    ti = world_interface(target, target_interface)
    compat = registry.interface_compatibility(si, ti)
    if not compat["compatible"]:
        raise ValueError("Incompatible interfaces: " + "; ".join(compat["reasons"]))
    R = _align(si.get("axis", [0, 0, 1]), [-v for v in ti["world_axis"]])
    sp = _mat_vec(R, si.get("position_mm", [0, 0, 0]))
    tp = ti["world_position_mm"]
    axis = ti["world_axis"]
    pos = [tp[k] - sp[k] + float(gap_mm) * axis[k] for k in range(3)]
    source.setdefault("transform", {})["position"] = pos
    source["transform"]["rotation_deg"] = _euler_xyz(R)
    source["transform"].setdefault("scale", [1, 1, 1])
    return {
        "source": source.get("id"),
        "source_interface": source_interface,
        "target": target.get("id"),
        "target_interface": target_interface,
        "compatibility": compat,
        "transform": deepcopy(source["transform"]),
    }


def connect_interfaces(project, a, ai, b, bi, connection_kind="auto"):
    ia, ib = object_interface(a, ai), object_interface(b, bi)
    compat = registry.interface_compatibility(ia, ib)
    if not compat["compatible"]:
        raise ValueError("Incompatible interfaces: " + "; ".join(compat["reasons"]))
    kind = connection_kind
    if kind == "auto":
        ik = str(ia.get("kind")) + str(ib.get("kind"))
        kind = "electrical" if (
            "electrical" in ik
            or any(x in str(ia.get("kind")) for x in ["digital", "servo_signal", "pwm", "i2c", "spi", "uart"])
        ) else "mechanical"
    item = {
        "id": __import__("uuid").uuid4().hex,
        "kind": kind,
        "a": {"object_id": a["id"], "interface_id": ai},
        "b": {"object_id": b["id"], "interface_id": bi},
        "compatibility": compat,
    }
    project.setdefault("connections", []).append(item)
    return item


def json_stable(x):
    import json
    return json.dumps(x, sort_keys=True, separators=(",", ":"), default=str)


def reality_check(project, object_lookup: Callable[[str], dict[str, Any]] | None = None):
    risks = []
    connections = project.get("connections", [])
    used = {
        (edge[side]["object_id"], edge[side]["interface_id"])
        for edge in connections
        for side in ("a", "b")
        if isinstance(edge.get(side), dict)
    }
    objs = [o for o in project.get("objects", []) if o.get("kind") == "component"]
    for obj in objs:
        c = component_definition(obj)
        if not c:
            risks.append({
                "severity": "error",
                "code": "component_missing_registry",
                "object_id": obj.get("id"),
                "message": f"{obj.get('name')} references missing component {obj.get('component_ref')}",
            })
            continue

        fidelity = c.get("geometry", {}).get("fidelity", "none")
        trust = int(c.get("trust_score", 0))
        if registry.GEOMETRY_RANK.get(fidelity, 0) < 55:
            risks.append({
                "severity": "warning",
                "code": "low_geometry_fidelity",
                "object_id": obj.get("id"),
                "message": f"{obj.get('name')} uses {fidelity} geometry; verify fit against vendor CAD.",
            })
        if c.get("geometry", {}).get("official_asset_expected") and _step_asset(c) is None:
            risks.append({
                "severity": "warning",
                "code": "official_geometry_asset_unavailable",
                "object_id": obj.get("id"),
                "message": f"{obj.get('name')} has manufacturer CAD expected but unavailable; ForgeCAD is using a fallback model.",
            })
        if trust < 55:
            risks.append({
                "severity": "warning",
                "code": "low_source_trust",
                "object_id": obj.get("id"),
                "message": f"{obj.get('name')} component data trust score is {trust}/100.",
            })

        for interface in obj.get("interfaces", c.get("interfaces", [])):
            if interface.get("required") and (obj.get("id"), interface.get("id")) not in used:
                risks.append({
                    "severity": "warning",
                    "code": "required_interface_open",
                    "object_id": obj.get("id"),
                    "interface_id": interface.get("id"),
                    "message": f"{obj.get('name')} required interface {interface.get('id')} is not connected.",
                })
        try:
            live = registry.component_by_id(obj.get("component_ref"))
            snap = obj.get("component_snapshot")
            if snap and json_stable({k: v for k, v in live.items() if k != "legacy"}) != json_stable(snap):
                risks.append({
                    "severity": "info",
                    "code": "registry_revision_changed",
                    "object_id": obj.get("id"),
                    "message": f"Registry data for {obj.get('name')} changed after this design snapshot; review before syncing.",
                })
        except KeyError:
            pass

    bom_refs = {x.get("component_ref") for x in project.get("bom", [])}
    for obj in objs:
        if obj.get("component_ref") not in bom_refs:
            risks.append({
                "severity": "warning",
                "code": "bom_missing_component",
                "object_id": obj.get("id"),
                "message": f"{obj.get('name')} is not represented in the BOM.",
            })
    return {
        "ok": not any(r["severity"] == "error" for r in risks),
        "risks": risks,
        "counts": {s: sum(r["severity"] == s for r in risks) for s in ["error", "warning", "info"]},
        "components": len(objs),
        "connections": len(connections),
    }
