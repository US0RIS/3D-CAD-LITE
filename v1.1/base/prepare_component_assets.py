from __future__ import annotations

"""Prepare high-fidelity built-in CAD assets used by ForgeCAD.

The build is intentionally deterministic about *what* component is represented:
- Raspberry Pi 5 uses Raspberry Pi Ltd's official STEP model.
- Raspberry Pi 4 Model B uses a detailed ForgeCAD parametric model driven by the
  official Raspberry Pi mechanical drawing, because Raspberry Pi publishes a
  mechanical drawing/DXF but not an official STEP model for Pi 4.

These files are bundled into the desktop application. Runtime design projects can
still register newer manufacturer STEP files through the component registry.
"""

from pathlib import Path
import io
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

    # Right-edge connector stack. Separate metal shells preserve the stepped Pi 4 silhouette.
    solids.extend([
        _box(21.0, 16.2, 13.5, 37.0, 17.75, 6.75, 0.6),   # RJ45 Ethernet
        _box(17.2, 14.8, 16.0, 38.4, -1.0, 8.0, 0.5),     # dual USB 3
        _box(17.2, 14.8, 16.0, 38.4, -19.0, 8.0, 0.5),    # dual USB 2
    ])
    # Approximate dark receptacle cavities; these are real voids, not just visual overlays.
    for cy in (17.75, -1.0, -19.0):
        cavity = _box(4.0, 10.5 if cy == 17.75 else 10.0, 8.0, 46.0, cy, 7.2, 0.4)
        solids.append(cavity)

    # Bottom-edge I/O from the official top-view layout.
    solids.extend([
        _box(9.0, 7.6, 3.2, -33.0, -29.0, 1.6, 0.7),     # USB-C power
        _box(7.6, 7.2, 3.0, -17.8, -29.0, 1.5, 0.4),     # micro-HDMI 0
        _box(7.6, 7.2, 3.0, -4.3, -29.0, 1.5, 0.4),      # micro-HDMI 1
        _box(10.4, 11.2, 5.5, 11.7, -27.0, 2.75, 0.8),   # 3.5 mm AV body
    ])
    solids.append(_cyl(6.2, 12.0, 11.7, -30.3, 2.9, axis="y"))

    # Camera/display FFC connectors and microSD card socket on the underside.
    solids.extend([
        _box(17.0, 3.6, 3.1, 5.0, 4.5, 2.35, 0.25),      # CSI
        _box(17.0, 3.6, 3.1, -31.0, 4.0, 2.35, 0.25),    # DSI
        _box(15.0, 13.0, 1.7, -34.5, 4.0, -1.65, 0.4),   # microSD underside
    ])

    # Major packages/shields. Dimensions are mechanical envelopes for interference and recognition.
    solids.extend([
        _box(15.5, 15.5, 2.2, -5.5, -1.0, 1.9, 0.35),    # BCM2711 SoC
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
    """Fetch Raspberry Pi Ltd's official Pi 5 STEP model and normalize its name."""
    req = urllib.request.Request(RPI5_STEP_URL, headers={"User-Agent": "ForgeCAD/1.1 component asset builder"})
    with urllib.request.urlopen(req, timeout=60) as response:
        payload = response.read()
    if len(payload) < 1_000_000:
        raise RuntimeError(f"Official Raspberry Pi 5 STEP archive unexpectedly small: {len(payload)} bytes")
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        candidates = [n for n in zf.namelist() if n.lower().endswith((".step", ".stp"))]
        if not candidates:
            raise RuntimeError("Official Raspberry Pi 5 archive contains no STEP file")
        # Prefer a non-graphics/smaller CAD file when multiple models exist.
        candidates.sort(key=lambda n: ("graphic" in n.lower(), len(n), n.lower()))
        data = zf.read(candidates[0])
    if len(data) < 1_000_000:
        raise RuntimeError(f"Official Raspberry Pi 5 STEP payload unexpectedly small: {len(data)} bytes")
    RPI5_OUT.write_bytes(data)


def verify_assets() -> None:
    for path in (RPI4_OUT, RPI5_OUT):
        if not path.is_file() or path.stat().st_size < 100_000:
            raise RuntimeError(f"Missing or implausible component asset: {path}")
        shape = cq.importers.importStep(str(path)).val()
        bb = shape.BoundingBox()
        if bb.xlen < 80 or bb.ylen < 50 or bb.zlen < 3:
            raise RuntimeError(
                f"Component asset has implausible envelope {path.name}: "
                f"{bb.xlen:.1f} x {bb.ylen:.1f} x {bb.zlen:.1f} mm"
            )


def main() -> None:
    build_raspberry_pi_4()
    fetch_raspberry_pi_5()
    verify_assets()
    print(f"Prepared high-fidelity component assets in {ASSET_DIR}")


if __name__ == "__main__":
    main()
