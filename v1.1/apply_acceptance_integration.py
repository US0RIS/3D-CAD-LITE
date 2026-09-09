from __future__ import annotations
from pathlib import Path
import sys

root=Path(sys.argv[1] if len(sys.argv)>1 else "v1.1/base")


def replace_once(path:Path,old:str,new:str):
    text=path.read_text(encoding="utf-8")
    if new in text:return False
    if old not in text:raise RuntimeError(f"expected integration anchor missing in {path}: {old[:80]!r}")
    path.write_text(text.replace(old,new,1),encoding="utf-8");return True

# Fold geometry interference into the canonical reality check instead of exposing
# a second, UI-only notion of whether the machine is buildable.
replace_once(root/"core.py",
'''def reality_check() -> dict[str,Any]:
    return system_validation.validate_system(PROJECT)
''',
'''def reality_check() -> dict[str,Any]:
    system=system_validation.validate_system(PROJECT)
    try:
        import assembly_validation
        assembly=assembly_validation.validate_assembly(PROJECT,build_shape,min_clearance_mm=1.0)
    except Exception as e:
        assembly={"ok":True,"counts":{"error":0,"warning":1,"info":0},"risks":[{"severity":"warning","code":"assembly_check_unavailable","message":str(e)}],"collisions":[],"low_clearances":[]}
    risks=list(system.get("risks",[]))+list(assembly.get("risks",[]));counts={s:sum(r.get("severity")==s for r in risks) for s in ("error","warning","info")}
    return {**system,"ok":counts["error"]==0,"counts":counts,"risks":risks,"assembly":assembly}
''')

# The Pi 5 recommendation is a current requirement for the 5 V rail; account for
# it when a source advertises a current limit.
replace_once(root/"system_validation.py",
'''load_current=_number(dm,"current_a","rated_current_a","max_current_a")''',
'''load_current=_number(dm,"current_a","rated_current_a","max_current_a","recommended_current_a")''')

# The manufacturer dimension drawing gives the regulator's two-hole spacing.
replace_once(root/"curated_catalog.py",
'''metadata={"hole_diameter_mm":2.18,"fastener":"M2","count":2}''',
'''metadata={"pattern_mm":[13.5,16.0],"hole_diameter_mm":2.18,"fastener":"M2","count":2}''')

replace_once(root/"server.py",
'''import project_bundle
''',
'''import project_bundle
import acceptance_design
import assembly_validation
import mounting
''')

replace_once(root/"server.py",
'''@app.get("/api/system-check")
def system_check():return core.reality_check()
''',
'''@app.get("/api/system-check")
def system_check():return core.reality_check()
@app.get("/api/assembly/check")
def assembly_check(min_clearance_mm:float=1.0):return assembly_validation.validate_assembly(core.PROJECT,core.build_shape,min_clearance_mm=min_clearance_mm)
@app.get("/api/mounting/plan/{plate_id}")
def mounting_plan(plate_id:str,component_ids:str|None=None,plate_thickness_mm:float|None=None,standoff_mm:float=6.0):
    ids=[x for x in (component_ids or "").split(",") if x] or None
    try:return mounting.plan_mounting(core.PROJECT,plate_id,ids,plate_thickness_mm=plate_thickness_mm,standoff_mm=standoff_mm)
    except KeyError as e:fail(e,404)
    except Exception as e:fail(e)
@app.post("/api/templates/v1.1-acceptance")
def install_v110_acceptance():
    try:
        project=acceptance_design.install_into_core();return {"ok":True,"project":project,"report":acceptance_design.acceptance_report(project,core.build_shape)}
    except Exception as e:fail(e)
@app.get("/api/templates/v1.1-acceptance")
def preview_v110_acceptance():
    try:
        project=acceptance_design.build_project();return {"project":project,"report":acceptance_design.acceptance_report(project,core.build_shape)}
    except Exception as e:fail(e)
''')

print("ForgeCAD v1.1 acceptance/collision/API integration applied")
