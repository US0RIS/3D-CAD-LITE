from __future__ import annotations
import os,tempfile
from pathlib import Path

_tmp=tempfile.TemporaryDirectory();os.environ["FORGECAD_DATA_DIR"]=_tmp.name
import cadquery as cq
import acceptance_design,component_registry as registry,core,project_bundle


def check(condition,message):
    if not condition:raise AssertionError(message)

project=acceptance_design.build_project();objects={o["id"]:o for o in project["objects"]}
check(len(objects)==6,"fabricated plate plus five real purchased components")
check({o.get("component_ref") for o in project["objects"] if o.get("component_ref")}==set(acceptance_design.COMPONENTS.values()),"all acceptance components are exact registry parts")
check(all((o.get("component_snapshot") or {}).get("trust_score",0)>=100 for o in project["objects"] if o.get("component_ref")),"purchased parts have manufacturer-trust frozen snapshots")

# Electrical/control graph: 12 V supply -> MOSFET + 5 V regulator, regulator -> Pi,
# Pi -> MOSFET signal, MOSFET -> solenoid.
check(len([e for e in project["connections"] if e.get("kind")=="electrical"])==5,"complete modeled electrical/control graph")
report=acceptance_design.acceptance_report(project,core.build_shape)
if not report["system"]["ok"]:raise AssertionError("system validation errors: "+str(report["system"]["risks"]))
if not report["assembly"]["ok"]:raise AssertionError("assembly collision errors: "+str(report["assembly"]["risks"]))

plate=objects[acceptance_design.IDS["plate"]];mount_holes=[f for f in plate.get("features",[]) if f.get("type")=="hole"]
check(len(mount_holes)>=8,"generated Pi mounting pattern plus chassis holes")
check(any(row.get("component_ref")=="fastener.m2p5x12" and int(row.get("qty",0))>=4 for row in project["bom"]),"automatic M2.5 fastener selection for Pi mounting stack")
check(any(x.get("object_id")==acceptance_design.IDS["supply"] for x in report["mounting_unresolved"]),"incomplete vendor mounting data remains explicit instead of invented")

# Fabricated geometry remains exportable while purchased parts remain immutable data.
step=Path(_tmp.name)/"acceptance_plate.step";cq.exporters.export(core.build_shape(plate),str(step),exportType="STEP");check(step.stat().st_size>100,"acceptance mounting plate STEP export")

# Portable project bundle round-trip preserves canonical project and frozen parts.
bundle=project_bundle.export_bundle_bytes(project);check(len(bundle)>500,"portable acceptance bundle generated")
restored=project_bundle.import_bundle_bytes(bundle);rp=restored["project"]
check(rp["name"]==project["name"] and len(rp["objects"])==len(project["objects"]),"portable bundle restores canonical assembly")
check({o.get("component_ref") for o in rp["objects"] if o.get("component_ref")}==set(acceptance_design.COMPONENTS.values()),"portable bundle preserves purchased component identity")

# The acceptance design can become the actual canonical workspace without a hidden
# UI-only representation.
installed=acceptance_design.install_into_core();check(installed["name"]==project["name"],"acceptance project installs into canonical core")
check(core.reality_check()["ok"],"installed acceptance assembly passes canonical reality/system validation")
print("ForgeCAD v1.1 real-system acceptance: PASS",{"objects":len(project["objects"]),"connections":len(project["connections"]),"bom_lines":len(project["bom"]),"warnings":report["system"]["counts"]["warning"],"mounting_unresolved":len(report["mounting_unresolved"])})
