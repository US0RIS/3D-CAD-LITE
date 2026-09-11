from __future__ import annotations

"""High-trust built-in component catalog for ForgeCAD.

Entries represent specific purchasable parts and tie engineering values and geometry
provenance to manufacturer/primary sources. Built-in STEP assets are bundled with
the desktop application when available.
"""

from pathlib import Path
import sys
from typing import Any


def source(url, title, kind="manufacturer", trust=100):
    return {
        "kind": kind,
        "trust": trust,
        "url": url,
        "title": title,
        "accessed": "2026-09-11",
    }


def iface(iid, kind, pos=(0, 0, 0), axis=(0, 0, 1), gender="neutral",
          mate=None, required=False, standard=None, metadata=None):
    d = {
        "id": iid,
        "kind": kind,
        "position_mm": [float(x) for x in pos],
        "axis": [float(x) for x in axis],
        "gender": gender,
        "required": required,
        "mate": list(mate or []),
    }
    if standard:
        d["standard"] = standard
    if metadata:
        d["metadata"] = metadata
    return d


def bundled_asset_path(filename: str) -> str:
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "component_assets" / filename)
    candidates.append(Path(__file__).resolve().parent / "component_assets" / filename)
    for path in candidates:
        if path.is_file():
            return str(path)
    # Keep a deterministic path even before build-time asset preparation.
    return str(candidates[0])


def step_asset(filename: str, url: str, *, official: bool) -> dict[str, Any]:
    kind = "manufacturer" if official else "forgecad_derived"
    trust = 100 if official else 75
    return {
        "id": filename.rsplit(".", 1)[0],
        "role": "geometry",
        "filename": filename,
        "path": bundled_asset_path(filename),
        "format": "step",
        "source": source(
            url,
            "Official manufacturer STEP" if official else "ForgeCAD parametric model from official mechanical drawing",
            kind=kind,
            trust=trust,
        ),
    }


def component(cid, category, manufacturer, model, dims, mass, *, mpn=None,
              tags=None, specs=None, profile=None, interfaces=None, url=None,
              title=None, procurement=None, official_step=False, assets=None,
              geometry_fidelity=None, programmable=False, platform=None):
    src = source(url, title or f"{manufacturer} {model}")
    assets = list(assets or [])
    fidelity = geometry_fidelity or ("official_step" if official_step and assets else "detailed_parametric")
    preferred = "step_asset" if assets else "parametric"
    return {
        "schema_version": 1,
        "id": cid,
        "category": category,
        "manufacturer": manufacturer,
        "model": model,
        "name": f"{manufacturer} {model}",
        "manufacturer_part_number": mpn or model,
        "revision": "manufacturer-current",
        "tags": list(tags or []),
        "dimensions_mm": [float(x) for x in dims],
        "mass_g": float(mass) if mass is not None else None,
        "material": None,
        "specs": dict(specs or {}),
        "geometry": {
            "preferred": preferred,
            "fidelity": fidelity,
            "trust": "manufacturer" if official_step else "forgecad_derived",
            "profile": profile or category,
            "dimensions_mm": [float(x) for x in dims],
            "assets": assets,
            "official_asset_expected": bool(official_step),
            "source": src,
        },
        "interfaces": list(interfaces or []),
        "keepouts": [],
        "procurement": dict(procurement or {}) | ({"url": url} if url else {}),
        "software": {"programmable": bool(programmable), "platform": platform},
        "provenance": [src],
        "trust_score": 100,
    }


RPI4_DRAWING = "https://pip-assets.raspberrypi.com/categories/545-raspberry-pi-4-model-b/documents/RP-008343-DS-1-raspberry-pi-4-mechanical-drawing.pdf"
RPI5_DRAWING = "https://pip-assets.raspberrypi.com/categories/892-raspberry-pi-5/documents/RP-008347-DS-1-raspberry-pi-5-mechanical-drawing.pdf"
RPI5_STEP = "https://pip-assets.raspberrypi.com/categories/892-raspberry-pi-5/documents/RP-010083-CA-1-rpi-5%203D%20STEP%20-%20No%20Graphics%20small%20file.zip"

CATALOG = [
    component(
        "compute.raspberry_pi_5_8gb", "compute", "Raspberry Pi", "5 8GB",
        [85, 56, 17], 46, mpn="SC1112",
        tags=["sbc", "linux", "gpio", "physical-cad", "official-step"],
        specs={
            "power_w": 12.0, "voltage_v": 5.0, "ram_gb": 8,
            "mounting_pattern_mm": [58.0, 49.0],
            "mount_hole_diameter_mm": 2.7,
        },
        profile="raspberry_pi_5",
        interfaces=[
            iface("mount", "mount_pattern", (0, 0, -0.8), (0, 0, -1),
                  mate=["board_standoffs", "mount_hole"], required=True,
                  metadata={"pattern_mm": [58, 49], "hole_diameter_mm": 2.7,
                            "hole_centers_mm": [[-39, -24.5], [-39, 24.5], [19, -24.5], [19, 24.5]],
                            "fastener": "M2.5"}),
            iface("gpio40", "digital_io", (-10, 24.2, 5.3), (0, 1, 0),
                  "bidirectional", ["digital_io", "pwm_output", "i2c", "spi", "uart"],
                  metadata={"pins": 40, "pitch_mm": 2.54, "logic_voltage_v": 3.3}),
            iface("usb_c_power", "electrical_power_input", (-31, -28, 2.5), (0, -1, 0),
                  "input", ["usb_c_source", "power_output"], True, "USB-C",
                  {"voltage_v": 5, "recommended_current_a": 5}),
            iface("micro_hdmi_0", "video_output", (-14, -28, 2.3), (0, -1, 0),
                  "output", ["micro_hdmi_sink"], standard="micro-HDMI"),
            iface("micro_hdmi_1", "video_output", (-2, -28, 2.3), (0, -1, 0),
                  "output", ["micro_hdmi_sink"], standard="micro-HDMI"),
            iface("ethernet", "ethernet", (42.5, -16.5, 7.5), (1, 0, 0),
                  "bidirectional", ["ethernet"], standard="RJ45"),
            iface("pcie_fpc", "pcie", (17.5, -23.5, 2.35), (0, -1, 0),
                  mate=["pcie"], metadata={"lanes": 1}),
            iface("fan_header", "fan_power", (25, 23, 2.45), (0, 1, 0),
                  mate=["fan"], metadata={"pins": 4}),
        ],
        url=RPI5_DRAWING, title="Raspberry Pi 5 mechanical drawing",
        procurement={"supplier": "Raspberry Pi Approved Resellers", "sku": "SC1112"},
        official_step=True,
        assets=[step_asset("raspberry_pi_5_official.step", RPI5_STEP, official=True)],
        programmable=True, platform="python/linux",
    ),
    component(
        "compute.raspberry_pi_4_model_b_8gb", "compute", "Raspberry Pi", "4 Model B 8GB",
        [85, 56, 16], 46, mpn="SC0195",
        tags=["sbc", "linux", "gpio", "physical-cad", "detailed-parametric"],
        specs={
            "power_w": 7.6, "voltage_v": 5.0, "ram_gb": 8,
            "mounting_pattern_mm": [58.0, 49.0],
            "mount_hole_diameter_mm": 2.7,
        },
        profile="raspberry_pi_4_model_b",
        interfaces=[
            iface("mount", "mount_pattern", (0, 0, -0.8), (0, 0, -1),
                  mate=["board_standoffs", "mount_hole"], required=True,
                  metadata={"pattern_mm": [58, 49], "hole_diameter_mm": 2.7,
                            "hole_centers_mm": [[-39, -24.5], [-39, 24.5], [19, -24.5], [19, 24.5]],
                            "fastener": "M2.5"}),
            iface("gpio40", "digital_io", (-10, 24.2, 5.3), (0, 1, 0),
                  "bidirectional", ["digital_io", "pwm_output", "i2c", "spi", "uart"],
                  metadata={"pins": 40, "pitch_mm": 2.54, "logic_voltage_v": 3.3}),
            iface("usb_c_power", "electrical_power_input", (-33, -28, 1.6), (0, -1, 0),
                  "input", ["usb_c_source", "power_output"], True, "USB-C",
                  {"voltage_v": 5, "recommended_current_a": 3}),
            iface("micro_hdmi_0", "video_output", (-17.8, -28, 1.5), (0, -1, 0),
                  "output", ["micro_hdmi_sink"], standard="micro-HDMI"),
            iface("micro_hdmi_1", "video_output", (-4.3, -28, 1.5), (0, -1, 0),
                  "output", ["micro_hdmi_sink"], standard="micro-HDMI"),
            iface("ethernet", "ethernet", (42.5, 17.75, 6.75), (1, 0, 0),
                  "bidirectional", ["ethernet"], standard="RJ45"),
            iface("camera", "camera_fpc", (5, 4.5, 2.35), (0, 1, 0), mate=["camera_fpc"]),
            iface("display", "display_fpc", (-31, 4, 2.35), (0, 1, 0), mate=["display_fpc"]),
        ],
        url=RPI4_DRAWING, title="Raspberry Pi 4 Model B mechanical drawing",
        procurement={"supplier": "Raspberry Pi Approved Resellers", "sku": "SC0195"},
        assets=[step_asset("raspberry_pi_4_model_b_parametric.step", RPI4_DRAWING, official=False)],
        geometry_fidelity="detailed_parametric",
        programmable=True, platform="python/linux",
    ),
    component(
        "motor.stepperonline.17hs19-2004s1", "stepper_motor", "StepperOnline", "17HS19-2004S1",
        [42, 42, 48], 390, mpn="17HS19-2004S1", tags=["nema17", "bipolar", "4-wire"],
        specs={"holding_torque_nm": 0.59, "rated_current_a": 2.0, "phase_resistance_ohm": 1.6,
               "inductance_mh": 3.0, "step_angle_deg": 1.8, "shaft_diameter_mm": 5.0,
               "shaft_length_mm": 24.0, "lead_length_mm": 1000, "insulation_class_c": 130},
        profile="stepper_motor",
        interfaces=[
            iface("mount_face", "mount_face", (0, 0, -24), (0, 0, -1), mate=["motor_mount"],
                  required=True, standard="NEMA17",
                  metadata={"hole_spacing_mm": [31, 31], "hole_diameter_mm": 3.0, "pattern": "4-hole-square"}),
            iface("output_shaft", "shaft", (0, 0, 36), (0, 0, 1), "male",
                  ["cylindrical_mate", "shaft_coupler"], True,
                  metadata={"diameter_mm": 5.0, "length_mm": 24.0, "d_cut_length_mm": 15.0}),
            iface("phases", "motor_power", (0, -21, 0), (0, -1, 0), "input", ["motor_output"],
                  True, metadata={"phases": 2, "rated_current_a": 2.0}),
        ],
        url="https://www.omc-stepperonline.com/nema-17-bipolar-59ncm-84oz-in-2a-42x48mm-4-wires-w-1m-cable-connector-17hs19-2004s1",
        title="17HS19-2004S1 product specification",
        procurement={"supplier": "StepperOnline", "sku": "17HS19-2004S1",
                     "unit_cost_usd": 9.62, "price_as_of": "2026-09-09"},
        official_step=True,
    ),
    component(
        "driver.pololu.g2_18v17", "motor_driver", "Pololu", "G2 High-Power Motor Driver 18v17",
        [33.0, 20.3, 8.0], 3.3, mpn="2991", tags=["h-bridge", "brushed-dc", "pwm"],
        specs={"input_min_v": 6.5, "input_max_v": 30.0, "recommended_max_v": 24.0,
               "continuous_current_a": 17.0, "logic_min_v": 1.8, "logic_max_v": 5.5,
               "max_pwm_hz": 100000, "current_sense_v_per_a": 0.02,
               "reverse_voltage_protection": True},
        profile="microcontroller",
        interfaces=[
            iface("vm", "electrical_power_input", (-16.5, 6, 0), (-1, 0, 0), "input",
                  ["electrical_power_output"], True,
                  metadata={"min_voltage_v": 6.5, "max_voltage_v": 30.0, "recommended_max_v": 24.0}),
            iface("motor", "motor_output", (16.5, 6, 0), (1, 0, 0), "output",
                  ["motor_power", "electrical_load"], True, metadata={"continuous_current_a": 17.0}),
            iface("pwm", "pwm_input", (0, -10.15, 0), (0, -1, 0), "input",
                  ["pwm_output", "digital_io"], True,
                  metadata={"logic_min_v": 1.8, "logic_max_v": 5.5, "max_frequency_hz": 100000}),
            iface("dir", "digital_input", (4, -10.15, 0), (0, -1, 0), "input", ["digital_io"], True),
        ],
        url="https://www.pololu.com/product/2991",
        title="Pololu G2 High-Power Motor Driver 18v17",
        procurement={"supplier": "Pololu", "sku": "2991", "unit_cost_usd": 44.95, "price_as_of": "2026-09-09"},
        official_step=True,
    ),
    component(
        "driver.adafruit.mosfet_5648", "load_driver", "Adafruit", "MOSFET Driver - STEMMA",
        [25.4, 17.7, 7.2], 2.4, mpn="5648",
        tags=["mosfet", "solenoid-driver", "motor-driver", "flyback-diode"],
        specs={"mosfet_max_v": 30.0, "continuous_load_a": 1.5, "peak_load_a": 3.0,
               "jst_continuous_a": 2.0, "flyback_diode": True},
        profile="microcontroller",
        interfaces=[
            iface("power_in", "electrical_power_input", (-12.7, 4, 0), (-1, 0, 0), "input",
                  ["electrical_power_output"], True, metadata={"max_voltage_v": 30.0}),
            iface("load_out", "switched_power", (12.7, 4, 0), (1, 0, 0), "output",
                  ["electrical_load"], True,
                  metadata={"continuous_current_a": 1.5, "peak_current_a": 3.0, "flyback_protected": True}),
            iface("signal", "digital_input", (0, -8.85, 0), (0, -1, 0), "input",
                  ["digital_io", "pwm_output"], True),
        ],
        url="https://www.adafruit.com/product/5648",
        title="Adafruit MOSFET Driver product page",
        procurement={"supplier": "Adafruit", "sku": "5648", "unit_cost_usd": 3.95, "price_as_of": "2026-09-09"},
    ),
    component(
        "solenoid.adafruit.412", "solenoid", "Adafruit", "Small Push-Pull Solenoid 12VDC",
        [30, 15, 13], 39, mpn="412", tags=["push-pull", "return-spring", "12v"],
        specs={"voltage_v": 12.0, "current_a": 0.30, "coil_resistance_ohm": 40.0,
               "stroke_mm": 5.5, "starting_force_n": 0.5, "retentive_force_n": 5.0,
               "duty_cycle": 1.0},
        profile="solenoid",
        interfaces=[
            iface("mount", "mount_face", (0, 0, -6.5), (0, 0, -1),
                  mate=["solenoid_mount", "mount_face"], required=True),
            iface("plunger", "linear_output", (0, 0, 12), (0, 0, 1), "male",
                  ["linkage", "push_surface"], True,
                  metadata={"stroke_mm": 5.5, "starting_force_n": 0.5}),
            iface("coil", "electrical_load", (15, 0, 0), (1, 0, 0), "input",
                  ["switched_power"], True,
                  metadata={"voltage_v": 12.0, "current_a": 0.30, "inductive": True}),
        ],
        url="https://www.adafruit.com/product/412",
        title="Adafruit Small Push-Pull Solenoid 12VDC",
        procurement={"supplier": "Adafruit", "sku": "412", "unit_cost_usd": 7.50, "price_as_of": "2026-09-09"},
    ),
    component(
        "power.meanwell.lrs_75_12", "power_supply", "MEAN WELL", "LRS-75-12",
        [99, 97, 30], 230, mpn="LRS-75-12", tags=["ac-dc", "12v", "open-frame"],
        specs={"input_ac_min_v": 85.0, "input_ac_max_v": 264.0, "output_v": 12.0,
               "max_current_a": 6.0, "rated_power_w": 72.0, "efficiency_percent": 89.0,
               "operating_temp_min_c": -30, "operating_temp_max_c": 70},
        profile="power_supply",
        interfaces=[
            iface("ac_in", "mains_power_input", (-49.5, -20, 0), (-1, 0, 0), "input",
                  ["mains_source"], True,
                  metadata={"min_vac": 85, "max_vac": 264, "hazardous_voltage": True}),
            iface("dc_out", "electrical_power_output", (49.5, -20, 0), (1, 0, 0), "output",
                  ["electrical_power_input", "power_input", "power_converter"], True,
                  metadata={"voltage_v": 12.0, "max_current_a": 6.0, "rated_power_w": 72.0}),
            iface("chassis", "mount_face", (0, 0, -15), (0, 0, -1),
                  mate=["mount_face", "power_supply_mount"], required=True,
                  metadata={"thread": "M3"}),
        ],
        url="https://www.meanwell.com/Upload/PDF/LRS-75/LRS-75-SPEC.PDF",
        title="MEAN WELL LRS-75 series specification",
        procurement={"supplier": "MEAN WELL", "sku": "LRS-75-12"},
    ),
    component(
        "power.pololu.d24v50f5", "power_converter", "Pololu",
        "5V 5A Step-Down Regulator D24V50F5", [17.8, 20.3, 8.8], 3.0, mpn="2851",
        tags=["buck", "5v", "5a", "dc-dc"],
        specs={"input_min_v": 6.0, "input_max_v": 38.0, "output_v": 5.0,
               "max_current_a": 5.0, "typical_efficiency_min_percent": 85.0,
               "typical_efficiency_max_percent": 95.0, "reverse_voltage_protection": True,
               "mount_hole_diameter_mm": 2.18},
        profile="microcontroller",
        interfaces=[
            iface("vin", "electrical_power_input", (-8.9, 5, 0), (-1, 0, 0), "input",
                  ["electrical_power_output"], True, metadata={"min_voltage_v": 6.0, "max_voltage_v": 38.0}),
            iface("vout", "electrical_power_output", (8.9, 5, 0), (1, 0, 0), "output",
                  ["electrical_power_input", "power_input"], True,
                  metadata={"voltage_v": 5.0, "max_current_a": 5.0}),
            iface("mount", "mount_pattern", (0, 0, -4.4), (0, 0, -1),
                  mate=["mount_hole", "board_standoffs"], required=True,
                  metadata={"pattern_mm": [13.5, 16.0], "hole_diameter_mm": 2.18,
                            "fastener": "M2", "count": 2}),
        ],
        url="https://www.pololu.com/product/2851",
        title="Pololu 5V, 5A Step-Down Voltage Regulator D24V50F5",
        procurement={"supplier": "Pololu", "sku": "2851", "unit_cost_usd": 32.95, "price_as_of": "2026-09-09"},
        official_step=True,
    ),
    component(
        "fan.noctua.nf_a4x10_5v", "fan", "Noctua", "NF-A4x10 5V",
        [40, 40, 11], 15, mpn="NF-A4x10 5V", tags=["40mm", "5v", "3-pin"],
        specs={"voltage_v": 5.0, "input_power_w": 0.22, "max_rpm": 4500,
               "airflow_cfm": 4.83, "static_pressure_mm_h2o": 1.78,
               "noise_dba": 17.9, "mounting_hole_spacing_mm": [32, 32]},
        profile="fan",
        interfaces=[
            iface("mount", "mount_pattern", (0, 0, -5.5), (0, 0, -1),
                  mate=["fan_mount", "mount_hole"], required=True,
                  metadata={"pattern_mm": [32, 32], "hole_diameter_mm": 4.3}),
            iface("power", "electrical_load", (20, 0, 0), (1, 0, 0), "input",
                  ["electrical_power_output", "fan_power"], True,
                  metadata={"voltage_v": 5.0, "typical_power_w": 0.22}),
            iface("air_in", "airflow", (0, 0, -5.5), (0, 0, 1), "input", ["airflow"]),
            iface("air_out", "airflow", (0, 0, 5.5), (0, 0, 1), "output", ["airflow"],
                  metadata={"airflow_cfm": 4.83}),
        ],
        url="https://www.noctua.at/en/products/nf-a4x10-5v/specifications",
        title="Noctua NF-A4x10 5V specifications",
        procurement={"supplier": "Noctua"},
    ),
    component(
        "bearing.skf.608_2z", "bearing", "SKF", "608-2Z", [22, 22, 7], 13,
        mpn="608-2Z", tags=["608", "shielded", "deep-groove"],
        specs={"bore_mm": 8.0, "outer_diameter_mm": 22.0, "width_mm": 7.0,
               "dynamic_load_kn": 3.45, "static_load_kn": 1.37,
               "reference_speed_rpm": 75000, "limiting_speed_rpm": 38000},
        profile="bearing",
        interfaces=[
            iface("shaft_bore", "cylindrical_mate", (0, 0, 0), (0, 0, 1), "female",
                  ["shaft"], True, metadata={"diameter_mm": 8.0}),
            iface("outer_race", "cylindrical_mate", (0, 0, 0), (0, 0, 1), "male",
                  ["bearing_pocket"], True, metadata={"diameter_mm": 22.0}),
        ],
        url="https://cdn.skfmediahub.skf.com/api/public/0901d196809a65c0/pdf_preview_medium/0901d196809a65c0_pdf_preview_medium.pdf",
        title="SKF rolling bearings catalog", procurement={"supplier": "SKF"},
    ),
]
