from __future__ import annotations

"""Prepare high-fidelity built-in CAD assets used by ForgeCAD.

The build is intentionally deterministic about *what* component is represented:
- Raspberry Pi 5 uses Raspberry Pi Ltd's official STEP model.
- Raspberry Pi 4 Model B uses a detailed ForgeCAD parametric model driven by the
  official Raspberry Pi mechanical drawing, because Raspberry Pi publishes a
  mechanical drawing/DXF but not an official STEP model for Pi 4.

All board assets use one ForgeCAD coordinate convention: PCB outline centred in
XY and PCB mid-plane at Z=0. Manufacturer STEP files are changed only by a rigid
rotation/translation when needed to reach that convention. That matters because
semantic interfaces (mounting holes, GPIO, power, video, etc.) must reference the
same geometry frame used by collision checks and exports.
"""

from pathlib import Path
import io
import tempfile
import urllib.request
import zipfile

import cadquery as cq

ROOT = Path(__file__).resolve().parent
ASSET_DIR = ROOT / "component_assets"
ASSET_DIR.mkdir(parents=True, exist_ok=True)

RPI5_STEP_URL = (
    "https://pip-assets.raspberrypi.com/categories/892-raspberry-pi-5/documents/"
    "RP-010083-CA-1-rpi-5%203D%20STEP%20-%20No%20Graphics%20small%20file.zip"
)
RPI5_OUT = ASSET_DIR / "raspberry_pi_5_official.step"
RPI4_OUT = ASSET_DIR / "raspberry_pi_4_model_b_parametric.step"
POLOLU_D24V50F5_STEP_URL = "https://www.pololu.com/file/0J1437/d24v50f5-step-down-voltage-regulator.step"
POLOLU_D24V50F5_OUT = ASSET_DIR / "pololu_d24v50f5_official.step"

BOARD_LENGTH_MM = 85.0
BOARD_WIDTH_MM = 56.0
BOARD_THICKNESS_NOMINAL_MM = 1.6


def _rounded_board(length: float, width: float, thickness: float, radius: float) -> cq.Shape:
    wp = cq.Workplane("XY").box(length, width, thickness, centered=(True, True, True))
    try:
        wp = wp.edges("|Z").fillet(radius)
    except Exception:
        pass
    return wp.val()


def _box(x, y, z, cx, cy, cz, radius=0.0) -> cq.Shape:
    wp = cq.Workplane("XY").box(float(x), float(y), float(z), centered=(True, True, True))
    if radius:
        try:
            wp = wp.edges("|Z").fillet(min(float(radius), x / 2 - 0.01, y / 2 - 0.01))
        except Exception:
            pass
    return wp.val().translate((float(cx), float(cy), float(cz)))


def _cyl(d, h, cx, cy, cz, axis="z") -> cq.Shape:
    if axis == "x":
        return cq.Workplane("YZ").circle(d / 2).extrude(h / 2, both=True).val().translate((cx, cy, cz))
    if axis == "y":
        return cq.Workplane("XZ").circle(d / 2).extrude(h / 2, both=True).val().translate((cx, cy, cz))
    return cq.Workplane("XY").circle(d / 2).extrude(h / 2, both=True).val().translate((cx, cy, cz))


def _find_pcb_solid(shape: cq.Shape) -> cq.Shape:
    """Find the 85 x 56 x ~1.6 mm PCB solid inside a board assembly."""
    candidates: list[tuple[float, cq.Shape]] = []
    for solid in shape.Solids():
        bb = solid.BoundingBox()
        planar = sorted((float(bb.xlen), float(bb.ylen)))
        if not (52.0 <= planar[0] <= 60.0 and 81.0 <= planar[1] <= 89.0):
            continue
        if not (0.6 <= float(bb.zlen) <= 3.2):
            continue
        score = (
            abs(planar[0] - BOARD_WIDTH_MM)
            + abs(planar[1] - BOARD_LENGTH_MM)
            + abs(float(bb.zlen) - BOARD_THICKNESS_NOMINAL_MM) * 2.0
        )
        candidates.append((score, solid))
    if not candidates:
        raise RuntimeError("Unable to identify the Raspberry Pi PCB solid in STEP geometry")
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _canonicalize_board_step(shape: cq.Shape) -> cq.Shape:
    """Rigidly align a manufacturer board model to ForgeCAD's board-centred frame."""
    board = _find_pcb_solid(shape)
    bb = board.BoundingBox()

    # Canonical X is the 85 mm board direction, Y is 56 mm. Rotate only if the
    # manufacturer file uses the opposite in-plane orientation.
    if bb.xlen < bb.ylen:
        shape = shape.rotate((0, 0, 0), (0, 0, 1), 90.0)
        board = _find_pcb_solid(shape)
        bb = board.BoundingBox()

    if not (81.0 <= bb.xlen <= 89.0 and 52.0 <= bb.ylen <= 60.0):
        raise RuntimeError(
            f"Manufacturer STEP PCB axes are not canonicalizable: {bb.xlen:.3f} x {bb.ylen:.3f} mm"
        )

    cx = (bb.xmin + bb.xmax) / 2.0
    cy = (bb.ymin + bb.ymax) / 2.0
    cz = (bb.zmin + bb.zmax) / 2.0
    canonical = shape.translate((-cx, -cy, -cz))

    check = _find_pcb_solid(canonical).BoundingBox()
    center = (
        (check.xmin + check.xmax) / 2.0,
        (check.ymin + check.ymax) / 2.0,
        (check.zmin + check.zmax) / 2.0,
    )
    if max(abs(v) for v in center) > 0.05:
        raise RuntimeError(f"Canonical STEP PCB is not centred: {center}")
    return canonical


def build_raspberry_pi_4() -> None:
    """Create a mechanically useful Raspberry Pi 4 Model B assembly.

    Coordinate convention is board-centred XY with the PCB mid-plane at Z=0.
    The 85 x 56 mm board outline, 3 mm corner radius and 58 x 49 mm M2.5
    mounting pattern come directly from Raspberry Pi's official drawing.
    Major connector envelopes and board components are represented separately so
    enclosure/interference work sees the real silhouette instead of proxy boxes.
    """

    solids: list[cq.Shape] = []

    board = _rounded_board(85.0, 56.0, 1.6, 3.0)
    # Official drawing: left holes 3.5 mm from board datum, 58 mm horizontal pitch,
    # 49 mm vertical pitch, 2.7 mm diameter.
    holes = [(-39.0, -24.5), (-39.0, 24.5), (19.0, -24.5), (19.0, 24.5)]
    for x, y in holes:
        cutter = cq.Workplane("XY").circle(1.35).extrude(3.0, both=True).val().translate((x, y, 0))
        board = board.cut(cutter)
    solids.append(board)

    # 40-pin GPIO: housing plus individually modelled 2.54 mm pitch pins.
    solids.append(_box(51.0, 5.1, 2.5, -10.0, 24.25, 2.05, 0.35))
    x0 = -34.13
    for col in range(20):
        for row in range(2):
            solids.append(_box(0.64, 0.64, 8.5, x0 + col * 2.54, 22.98 + row * 2.54, 5.3, 0.08))

    # Right-edge connector stack. Heights are taken from the official mechanical drawing.
    solids.extend([
        _box(21.0, 16.2, 13.5, 37.0, 17.75, 7.55, 0.6),  # RJ45, 13.5 mm above PCB top
        _box(17.2, 14.8, 16.0, 38.4, -1.0, 8.8, 0.5),     # dual USB 3, 16.0 mm above PCB top
        _box(17.2, 14.8, 16.0, 38.4, -19.0, 8.8, 0.5),    # dual USB 2, 16.0 mm above PCB top
    ])

    # Bottom-edge I/O from the official top-view layout.
    solids.extend([
        _box(9.0, 7.6, 3.2, -33.0, -29.0, 2.4, 0.7),     # USB-C power, 3.2 mm above PCB top
        _box(7.6, 7.2, 3.0, -17.8, -29.0, 2.3, 0.4),     # micro-HDMI 0, 3.0 mm above PCB top
        _box(7.6, 7.2, 3.0, -4.3, -29.0, 2.3, 0.4),      # micro-HDMI 1, 3.0 mm above PCB top
        _box(10.4, 11.2, 5.5, 11.7, -27.0, 3.55, 0.8),   # 3.5 mm AV body, 5.5 mm above PCB top
    ])
    solids.append(_cyl(6.2, 12.0, 11.7, -30.3, 3.0, axis="y"))

    # Camera/display FFC connectors and microSD card socket on the underside.
    solids.extend([
        _box(17.0, 3.6, 3.1, 5.0, 4.5, 2.35, 0.25),      # CSI
        _box(17.0, 3.6, 3.1, -31.0, 4.0, 2.35, 0.25),    # DSI
        _box(15.0, 13.0, 1.7, -34.5, 4.0, -1.65, 0.4),   # microSD underside
    ])

    # Major packages/shields. Dimensions are mechanical envelopes for interference and recognition.
    solids.extend([
        _box(15.5, 15.5, 2.4, -5.5, -1.0, 2.0, 0.35),    # BCM2711 SoC: drawing Z=2.4 above PCB top
        _box(12.5, 10.5, 1.5, 12.0, -1.0, 1.55, 0.25),   # SDRAM
        _box(9.0, 9.0, 1.4, 19.5, 11.0, 1.5, 0.25),      # USB controller
        _box(14.5, 12.5, 1.4, -27.0, 11.5, 1.5, 0.25),   # PMIC / support package area
        _box(15.0, 12.5, 2.0, -31.5, 18.0, 1.8, 0.4),    # RF shield/module
        _box(4.0, 2.0, 1.8, -22.0, 18.0, 1.7, 0.2),      # crystal / oscillator envelope
    ])

    # Representative passive banks so the model reads as a PCB and gives conservative local height.
    for i in range(7):
        solids.append(_box(2.0, 1.0, 1.1, -24.0 + i * 3.2, -10.5, 1.35, 0.15))
    for i in range(6):
        solids.append(_box(1.8, 0.9, 1.0, 7.5 + i * 2.8, 16.0, 1.3, 0.12))

    assembly = cq.Compound.makeCompound(solids)
    cq.exporters.export(assembly, str(RPI4_OUT))


def fetch_raspberry_pi_5() -> None:
    """Fetch and rigidly canonicalize Raspberry Pi Ltd's official Pi 5 STEP model."""
    req = urllib.request.Request(RPI5_STEP_URL, headers={"User-Agent": "ForgeCAD/1.1 component asset builder"})
    with urllib.request.urlopen(req, timeout=60) as response:
        payload = response.read()
    if len(payload) < 1_000_000:
        raise RuntimeError(f"Official Raspberry Pi 5 STEP archive unexpectedly small: {len(payload)} bytes")

    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        candidates = [n for n in zf.namelist() if n.lower().endswith((".step", ".stp"))]
        if not candidates:
            raise RuntimeError("Official Raspberry Pi 5 archive contains no STEP file")
        candidates.sort(key=lambda n: ("graphic" in n.lower(), len(n), n.lower()))
        data = zf.read(candidates[0])
    if len(data) < 1_000_000:
        raise RuntimeError(f"Official Raspberry Pi 5 STEP payload unexpectedly small: {len(data)} bytes")

    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / "rpi5-manufacturer.step"
        raw.write_bytes(data)
        shape = cq.importers.importStep(str(raw)).val()
        canonical = _canonicalize_board_step(shape)
        cq.exporters.export(canonical, str(RPI5_OUT))



def fetch_pololu_d24v50f5() -> None:
    """Fetch Pololu's official D24V50F5 STEP and align it to ForgeCAD's centred frame."""
    req = urllib.request.Request(
        POLOLU_D24V50F5_STEP_URL,
        headers={"User-Agent": "ForgeCAD/1.1 component asset builder"},
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        payload = response.read()
    if len(payload) < 1_000_000:
        raise RuntimeError(f"Official Pololu D24V50F5 STEP unexpectedly small: {len(payload)} bytes")

    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / "pololu-d24v50f5-manufacturer.step"
        raw.write_bytes(payload)
        shape = cq.importers.importStep(str(raw)).val()
        bb = shape.BoundingBox()

        direct_error = abs(float(bb.xlen) - 17.8) + abs(float(bb.ylen) - 20.3)
        swapped_error = abs(float(bb.xlen) - 20.3) + abs(float(bb.ylen) - 17.8)
        if swapped_error < direct_error:
            shape = shape.rotate((0, 0, 0), (0, 0, 1), 90.0)
            bb = shape.BoundingBox()

        cx = (bb.xmin + bb.xmax) / 2.0
        cy = (bb.ymin + bb.ymax) / 2.0
        cz = (bb.zmin + bb.zmax) / 2.0
        canonical = shape.translate((-cx, -cy, -cz))
        check = canonical.BoundingBox()
        if abs(float(check.xlen) - 17.8) > 1.0 or abs(float(check.ylen) - 20.3) > 1.0:
            raise RuntimeError(
                f"Official Pololu STEP has unexpected XY envelope: {check.xlen:.3f} x {check.ylen:.3f} mm"
            )
        if not 5.0 <= float(check.zlen) <= 12.0:
            raise RuntimeError(f"Official Pololu STEP has unexpected Z envelope: {check.zlen:.3f} mm")
        cq.exporters.export(canonical, str(POLOLU_D24V50F5_OUT))

def _verify_board_frame(path: Path) -> tuple[float, float, float]:
    shape = cq.importers.importStep(str(path)).val()
    board = _find_pcb_solid(shape)
    bb = board.BoundingBox()
    cx = (bb.xmin + bb.xmax) / 2.0
    cy = (bb.ymin + bb.ymax) / 2.0
    cz = (bb.zmin + bb.zmax) / 2.0
    if max(abs(cx), abs(cy), abs(cz)) > 0.05:
        raise RuntimeError(f"{path.name}: PCB frame is not canonical: center=({cx:.3f},{cy:.3f},{cz:.3f})")
    if abs(bb.xlen - BOARD_LENGTH_MM) > 2.0 or abs(bb.ylen - BOARD_WIDTH_MM) > 2.0:
        raise RuntimeError(f"{path.name}: PCB size is not 85 x 56 mm: {bb.xlen:.3f} x {bb.ylen:.3f}")
    overall = shape.BoundingBox()
    return overall.xlen, overall.ylen, overall.zlen


def verify_assets() -> None:
    for path in (RPI4_OUT, RPI5_OUT):
        if not path.is_file() or path.stat().st_size < 100_000:
            raise RuntimeError(f"Missing or implausible component asset: {path}")
        x, y, z = _verify_board_frame(path)
        if x < 80 or y < 50 or z < 3:
            raise RuntimeError(
                f"Component asset has implausible envelope {path.name}: {x:.1f} x {y:.1f} x {z:.1f} mm"
            )
        print(f"Verified {path.name}: envelope {x:.2f} x {y:.2f} x {z:.2f} mm; PCB frame canonical")

    if not POLOLU_D24V50F5_OUT.is_file() or POLOLU_D24V50F5_OUT.stat().st_size < 1_000_000:
        raise RuntimeError(f"Missing or implausible component asset: {POLOLU_D24V50F5_OUT}")
    pololu = cq.importers.importStep(str(POLOLU_D24V50F5_OUT)).val().BoundingBox()
    if abs(float(pololu.xlen) - 17.8) > 1.0 or abs(float(pololu.ylen) - 20.3) > 1.0 or not 5.0 <= float(pololu.zlen) <= 12.0:
        raise RuntimeError(
            f"Pololu D24V50F5 asset has implausible envelope: {pololu.xlen:.2f} x {pololu.ylen:.2f} x {pololu.zlen:.2f} mm"
        )
    print(f"Verified {POLOLU_D24V50F5_OUT.name}: envelope {pololu.xlen:.2f} x {pololu.ylen:.2f} x {pololu.zlen:.2f} mm; manufacturer STEP")


def main() -> None:
    build_raspberry_pi_4()
    fetch_raspberry_pi_5()
    fetch_pololu_d24v50f5()
    verify_assets()
    print(f"Prepared high-fidelity component assets in {ASSET_DIR}")


if __name__ == "__main__":
    main()
