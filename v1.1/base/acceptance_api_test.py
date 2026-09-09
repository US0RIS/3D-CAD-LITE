from __future__ import annotations
import io,os,tempfile
_tmp=tempfile.TemporaryDirectory();os.environ["FORGECAD_DATA_DIR"]=_tmp.name
from fastapi.testclient import TestClient
import acceptance_design,core,server

client=TestClient(server.app)

def check(cond,msg):
    if not cond:raise AssertionError(msg)

def get(path):
    r=client.get(path);check(r.status_code==200,f"GET {path}: {r.status_code} {r.text}");return r

def post(path,**kwargs):
    r=client.post(path,**kwargs);check(r.status_code==200,f"POST {path}: {r.status_code} {r.text}");return r

preview=get("/api/templates/v1.1-acceptance").json();check(preview["project"]["name"].startswith("ForgeCAD v1.1"),"acceptance template preview");check(preview["report"]["system"]["ok"],"preview electromechanical validation");check(preview["report"]["assembly"]["ok"],"preview geometric collision validation")

installed=post("/api/templates/v1.1-acceptance").json();check(installed["ok"] and installed["project"]["name"]==preview["project"]["name"],"install acceptance template through API");check(len(installed["project"]["objects"])==6,"canonical acceptance object count")

system=get("/api/system-check").json();check(system["ok"],"canonical system check");check("assembly" in system and system["assembly"]["ok"],"canonical reality check includes assembly geometry")
assembly=get("/api/assembly/check?min_clearance_mm=1.0").json();check(assembly["ok"] and not assembly["collisions"],"assembly endpoint collision-free")

plate=acceptance_design.IDS["plate"];pi=acceptance_design.IDS["pi"];buck=acceptance_design.IDS["buck"]
plan=get(f"/api/mounting/plan/{plate}?component_ids={pi},{buck}&standoff_mm=6").json();check(any(m["object_id"]==pi and len(m["points_mm"])==4 for m in plan["mounts"]),"API mounting planner returns verified Pi four-hole pattern");check(any(x["object_id"]==buck for x in plan["unresolved"]),"ambiguous two-hole regulator pattern remains unresolved")

bundle=get("/api/project/bundle");check(bundle.headers.get("content-type"," ").startswith("application/zip") and len(bundle.content)>500,"portable bundle API")
restored=post("/api/project/import-bundle",files={"file":("acceptance.forgecad.zip",bundle.content,"application/zip")}).json();check(restored["project"]["name"]==preview["project"]["name"],"bundle API round trip")
check(get("/api/system-check").json()["ok"],"restored bundle remains buildability-valid")

print("ForgeCAD v1.1 acceptance API: PASS",{"paths":len(server.app.openapi()["paths"]),"objects":len(core.PROJECT["objects"]),"connections":len(core.PROJECT["connections"])})
