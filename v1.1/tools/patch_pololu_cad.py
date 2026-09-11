from pathlib import Path

prepare = Path("v1.1/base/prepare_component_assets.py")
text = prepare.read_text()

old = 'RPI4_OUT = ASSET_DIR / "raspberry_pi_4_model_b_parametric.step"\n'
new = old + (
    'POLOLU_D24V50F5_STEP_URL = "https://www.pololu.com/file/0J1437/d24v50f5-step-down-voltage-regulator.step"\n'
    'POLOLU_D24V50F5_OUT = ASSET_DIR / "pololu_d24v50f5_official.step"\n'
)
if "POLOLU_D24V50F5_STEP_URL" not in text:
    if old not in text:
        raise SystemExit("prepare_component_assets.py constants anchor not found")
    text = text.replace(old, new, 1)

function = '''

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
'''
anchor = "\ndef _verify_board_frame(path: Path) -> tuple[float, float, float]:\n"
if "def fetch_pololu_d24v50f5()" not in text:
    if anchor not in text:
        raise SystemExit("prepare_component_assets.py function anchor not found")
    text = text.replace(anchor, function + anchor, 1)

old_verify = '''def verify_assets() -> None:
    for path in (RPI4_OUT, RPI5_OUT):
        if not path.is_file() or path.stat().st_size < 100_000:
            raise RuntimeError(f"Missing or implausible component asset: {path}")
        x, y, z = _verify_board_frame(path)
        if x < 80 or y < 50 or z < 3:
            raise RuntimeError(
                f"Component asset has implausible envelope {path.name}: {x:.1f} x {y:.1f} x {z:.1f} mm"
            )
        print(f"Verified {path.name}: envelope {x:.2f} x {y:.2f} x {z:.2f} mm; PCB frame canonical")
'''
new_verify = old_verify + '''
    if not POLOLU_D24V50F5_OUT.is_file() or POLOLU_D24V50F5_OUT.stat().st_size < 1_000_000:
        raise RuntimeError(f"Missing or implausible component asset: {POLOLU_D24V50F5_OUT}")
    pololu = cq.importers.importStep(str(POLOLU_D24V50F5_OUT)).val().BoundingBox()
    if abs(float(pololu.xlen) - 17.8) > 1.0 or abs(float(pololu.ylen) - 20.3) > 1.0 or not 5.0 <= float(pololu.zlen) <= 12.0:
        raise RuntimeError(
            f"Pololu D24V50F5 asset has implausible envelope: {pololu.xlen:.2f} x {pololu.ylen:.2f} x {pololu.zlen:.2f} mm"
        )
    print(f"Verified {POLOLU_D24V50F5_OUT.name}: envelope {pololu.xlen:.2f} x {pololu.ylen:.2f} x {pololu.zlen:.2f} mm; manufacturer STEP")
'''
if "Pololu D24V50F5 asset has implausible envelope" not in text:
    if old_verify not in text:
        raise SystemExit("prepare_component_assets.py verify anchor not found")
    text = text.replace(old_verify, new_verify, 1)

old_main = '''def main() -> None:
    build_raspberry_pi_4()
    fetch_raspberry_pi_5()
    verify_assets()
'''
new_main = '''def main() -> None:
    build_raspberry_pi_4()
    fetch_raspberry_pi_5()
    fetch_pololu_d24v50f5()
    verify_assets()
'''
if "    fetch_pololu_d24v50f5()\n" not in text:
    if old_main not in text:
        raise SystemExit("prepare_component_assets.py main anchor not found")
    text = text.replace(old_main, new_main, 1)
prepare.write_text(text)

catalog = Path("v1.1/base/curated_catalog.py")
text = catalog.read_text()
old = '''        procurement={"supplier": "Pololu", "sku": "2851", "unit_cost_usd": 32.95, "price_as_of": "2026-09-09"},
        official_step=True,
'''
new = '''        procurement={"supplier": "Pololu", "sku": "2851", "unit_cost_usd": 32.95, "price_as_of": "2026-09-09"},
        official_step=True,
        assets=[step_asset(
            "pololu_d24v50f5_official.step",
            "https://www.pololu.com/file/0J1437/d24v50f5-step-down-voltage-regulator.step",
            official=True,
        )],
'''
if "pololu_d24v50f5_official.step" not in text:
    if old not in text:
        raise SystemExit("curated_catalog.py Pololu anchor not found")
    text = text.replace(old, new, 1)
catalog.write_text(text)

print("Patched official Pololu D24V50F5 CAD asset pipeline")
