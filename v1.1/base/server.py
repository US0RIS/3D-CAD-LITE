from __future__ import annotations
import io, json, os, re, zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any
import cadquery as cq
from fastapi import Body, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import agents, analysis, core, jarvis_bridge, software
import component_registry as components
import component_importers
import physical_components
import project_bundle
import acceptance_design
import assembly_validation
import mounting

ROOT=Path(__file__).resolve().parent;STATIC=ROOT/"static"
class Command(BaseModel): op:str; args:dict[str,Any]=Field(default_factory=dict); actor:str="human"; reason:str=""
class AgentMessage(BaseModel): text:str; model:str|None=None; role:str="designer"; execute:bool=True
class ChatMessage(BaseModel): text:str; model:str|None=None; selected_id:str|None=None; execute:bool=False
class ComponentSearchBody(BaseModel): query:str=""; category:str|None=None; constraints:dict[str,Any]=Field(default_factory=dict); weights:dict[str,float]=Field(default_factory=dict); limit:int=20; include_infeasible:bool=True; min_trust:int=0; min_geometry_fidelity:str|None=None
class ComponentSelectBody(BaseModel): query:str=""; category:str|None=None; requirements:dict[str,Any]=Field(default_factory=dict); limit:int=8
class MateBody(BaseModel): source_id:str; source_interface:str; target_id:str; target_interface:str; gap_mm:float=0
class ConnectBody(BaseModel): a_id:str; a_interface:str; b_id:str; b_interface:str; kind:str="auto"
class CodeFileBody(BaseModel): path:str; content:str=""
class CodeRenameBody(BaseModel): old_path:str; new_path:str
class DesignStatusBody(BaseModel): name:str; status:str; note:str=""; physical_verified:bool=False
class OptimizeBody(BaseModel): variables:list[dict[str,Any]]; objective:str="mass"; force_n:float=100; axis:str="x"; deflection_max_mm:float|None=None; yield_fos_min:float|None=None; max_evals:int=90
class JarvisChangeBody(BaseModel): text:str; model:str|None=None; execute:bool=True; always_branch:bool=True
class JarvisComponentBody(BaseModel): category:str|None=None; constraints:dict[str,Any]=Field(default_factory=dict); weights:dict[str,float]=Field(default_factory=dict); query:str=""
class JarvisAnalysisBody(BaseModel): kind:str; object_id:str|None=None; params:dict[str,Any]=Field(default_factory=dict)

app=FastAPI(title="ForgeCAD Engineering API",version=core.APP_VERSION,description="AI-native local CAD/CAE workbench with one canonical model shared by humans, local agents and Jarvis.")
app.mount("/static",StaticFiles(directory=STATIC),name="static")
def fail(e,status=400):raise HTTPException(status,str(e))
def require_jarvis(key:str|None=Header(default=None,alias="X-ForgeCAD-Jarvis-Key")):
    if not jarvis_bridge.verify_token(key):raise HTTPException(401,"Invalid ForgeCAD Jarvis bridge credential")
def safe_name(obj):return re.sub(r"[^A-Za-z0-9_-]+","_",obj.get("name","part")).strip("_") or "part"

@app.get("/")
def root():return FileResponse(STATIC/"index.html",headers={"Cache-Control":"no-store, max-age=0"})
@app.get("/api/health")
def health():return {"ok":True,"service":"ForgeCAD","version":core.APP_VERSION,"build_id":os.environ.get("FORGECAD_BUILD_ID","forgecad-v1"),"ollama_model":os.environ.get("FORGECAD_OLLAMA_MODEL","qwen3:8b"),"active_design":core.ACTIVE_DESIGN}
@app.get("/api/project")
def project():return core.PROJECT
@app.post("/api/project/reset")
def reset():return core.reset_project()
@app.post("/api/project/import-json")
def import_json(payload:dict[str,Any]=Body(...)):
    try:
        st=core.upgrade_project(payload);core.PROJECT.clear();core.PROJECT.update(st);core.push_history("import project JSON","human","replace canonical project state");core.persist();return core.PROJECT
    except Exception as e:fail(e)
@app.get("/api/export")
def export():return core.PROJECT
@app.get("/api/project/bundle")
def export_bundle():
    data=project_bundle.export_bundle_bytes(core.PROJECT);return Response(content=data,media_type="application/zip",headers={"Content-Disposition":"attachment; filename=ForgeCAD-project.forgecad.zip"})
@app.post("/api/project/import-bundle")
async def import_bundle(file:UploadFile=File(...)):
    try:
        result=project_bundle.import_bundle_bytes(await file.read());st=core.upgrade_project(result["project"]);core.PROJECT.clear();core.PROJECT.update(st);core.push_history("import portable project bundle","human","restore canonical project plus component assets");core.persist();result["project"]=core.PROJECT;return result
    except Exception as e:fail(e)
@app.post("/api/import/step")
async def import_step(file:UploadFile=File(...)):
    try:
        data=await file.read()
        if len(data)>100*1024*1024:raise ValueError("STEP file exceeds 100 MB")
        return {"ok":True,"object":core.import_step_bytes(file.filename or "import.step",data)}
    except Exception as e:fail(e)
@app.post("/api/command")
def command(c:Command):
    try:return core.execute(c.op,c.args,c.actor,c.reason)
    except KeyError as e:fail(e,404)
    except Exception as e:fail(e)
@app.post("/api/undo")
def undo():return {"ok":core.undo(),"project":core.PROJECT}
@app.post("/api/redo")
def redo():return {"ok":core.redo(),"project":core.PROJECT}
@app.get("/api/materials")
def materials():return core.MATERIALS
@app.get("/api/mesh/{object_id}")
def mesh(object_id:str,tolerance:float=.35):
    try:return core.tessellate(core.object_by_id(object_id),tolerance)
    except KeyError as e:fail(e,404)
    except Exception as e:fail(e)
@app.get("/api/metrics")
def metrics():
    try:return {"project":core.project_metrics(),"objects":{o["id"]:core.object_metrics(o) for o in core.PROJECT["objects"]}}
    except Exception as e:fail(e)
@app.get("/api/requirements/check")
def reqs():return core.requirement_checks()
@app.get("/api/history")
def history(limit:int=50):return list(reversed(core.PROJECT.get("ledger",[])[-max(1,min(limit,200)):]))

@app.get("/api/branches")
def branches():return core.list_branches()
@app.post("/api/branch")
def branch(c:Command):
    try:return {"ok":True,"project":core.create_branch(str(c.args.get("name","branch")),reason=c.reason)}
    except Exception as e:fail(e)
@app.post("/api/branch/switch")
def switch(c:Command):
    try:return {"ok":True,"project":core.switch_branch(str(c.args.get("name","main")))}
    except KeyError as e:fail(e,404)
@app.get("/api/branch/compare/{name}")
def compare(name:str,other:str|None=None):
    try:return core.compare_branch(name,other)
    except KeyError as e:fail(e,404)
@app.post("/api/design/status")
def design_status(body:DesignStatusBody):
    try:return core.set_design_status(body.name,body.status,body.note,body.physical_verified)
    except KeyError as e:fail(e,404)

@app.get("/api/components")
def comp_list(category:str|None=None):
    stats=components.registry_stats();return {"categories":components.categories(),"total":stats["total"],"stats":stats,"results":components.all_components(category)}
@app.get("/api/components/schema")
def comp_schema():return components.component_schema()
@app.get("/api/components/stats")
def comp_stats():return components.registry_stats()
@app.get("/api/components/providers")
def comp_providers():return components.provider_status()
@app.post("/api/components/search")
def comp_search(body:ComponentSearchBody):return components.search_components(body.query,body.category,body.constraints,body.weights,body.limit,body.include_infeasible,body.min_trust,body.min_geometry_fidelity)
@app.post("/api/components/select")
def comp_select(body:ComponentSelectBody):return components.select_component(body.requirements,category=body.category,query=body.query,limit=body.limit)
@app.post("/api/components/import")
def comp_import(payload:dict[str,Any]|list[dict[str,Any]]=Body(...)):
    try:return components.import_components(payload)
    except Exception as e:fail(e)
@app.post("/api/components/import-pack")
async def comp_import_pack(file:UploadFile=File(...)):
    try:return components.import_catalog_pack_bytes(file.filename or "catalog.json",await file.read())
    except Exception as e:fail(e)
@app.post("/api/components/import-step-component")
async def comp_import_step_component(file:UploadFile=File(...),manufacturer:str="Custom",model:str="Vendor Component",category:str="custom",component_id:str|None=None,manufacturer_part_number:str|None=None,mass_g:float|None=None,source_kind:str="user_supplied",source_url:str|None=None):
    try:return component_importers.import_step_component(file.filename or "component.step",await file.read(),manufacturer=manufacturer,model=model,category=category,component_id=component_id,manufacturer_part_number=manufacturer_part_number,mass_g=mass_g,source_kind=source_kind,source_url=source_url)
    except Exception as e:fail(e)
@app.get("/api/components/{component_id}")
def comp_get(component_id:str):
    try:return components.component_by_id(component_id)
    except KeyError as e:fail(e,404)
@app.get("/api/components/{component_id}/compatible/{other_id}")
def comp_compatible(component_id:str,other_id:str):
    try:return {"a":component_id,"b":other_id,"interfaces":components.compatible_interfaces(component_id,other_id)}
    except KeyError as e:fail(e,404)
@app.post("/api/components/{component_id}/asset")
async def comp_asset(component_id:str,file:UploadFile=File(...),role:str="geometry",source_kind:str="user_supplied",source_url:str|None=None):
    try:return components.register_asset_bytes(component_id,file.filename or "asset.step",await file.read(),role=role,source_kind=source_kind,source_url=source_url)
    except KeyError as e:fail(e,404)
    except Exception as e:fail(e)
@app.post("/api/components/add/{component_id}")
def comp_add(component_id:str):
    try:return core.execute("add_component",{"component_id":component_id},"human",f"add purchased component {component_id}")
    except KeyError as e:fail(e,404)
    except Exception as e:fail(e)
@app.post("/api/components/sync/{object_id}")
def comp_sync(object_id:str):
    try:return core.execute("sync_component",{"id":object_id},"human","explicitly sync component registry snapshot")
    except KeyError as e:fail(e,404)
    except Exception as e:fail(e)
@app.post("/api/assembly/mate")
def assembly_mate(body:MateBody):
    try:return core.execute("mate_components",body.model_dump(),"human","mate real-world component interfaces")
    except KeyError as e:fail(e,404)
    except Exception as e:fail(e)
@app.post("/api/connections")
def connection_add(body:ConnectBody):
    try:return core.execute("connect_interfaces",body.model_dump(),"human","connect component interfaces")
    except KeyError as e:fail(e,404)
    except Exception as e:fail(e)
@app.delete("/api/connections/{connection_id}")
def connection_delete(connection_id:str):
    try:return core.execute("disconnect",{"id":connection_id},"human","remove interface connection")
    except KeyError as e:fail(e,404)
@app.get("/api/reality-check")
def reality_check():return core.reality_check()
@app.get("/api/system-check")
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

@app.get("/api/code/{object_id}")
def code_ws(object_id:str,include_contents:bool=True):
    try:
        ws=software.workspace_for_object(core.PROJECT,object_id)
        if not ws:raise KeyError("Selected component has no code workspace")
        return software.summarize_workspace(ws,include_contents)
    except KeyError as e:fail(e,404)
@app.get("/api/code/{object_id}/file")
def code_read(object_id:str,path:str):
    try:return software.read_file(core.PROJECT,object_id,path)
    except KeyError as e:fail(e,404)
@app.post("/api/code/{object_id}/file")
def code_write(object_id:str,body:CodeFileBody):
    try:return core.execute("code_write",{"id":object_id,"path":body.path,"content":body.content},"human","edit code in ForgeCAD IDE")
    except KeyError as e:fail(e,404)
    except Exception as e:fail(e)
@app.delete("/api/code/{object_id}/file")
def code_delete(object_id:str,path:str):
    try:return core.execute("code_delete",{"id":object_id,"path":path},"human","delete code in ForgeCAD IDE")
    except KeyError as e:fail(e,404)
@app.post("/api/code/{object_id}/rename")
def code_rename(object_id:str,body:CodeRenameBody):
    try:return core.execute("code_rename",{"id":object_id,"old_path":body.old_path,"new_path":body.new_path},"human","rename code in ForgeCAD IDE")
    except KeyError as e:fail(e,404)
@app.post("/api/code/{object_id}/validate")
def code_validate(object_id:str):
    try:return software.validate_workspace(core.PROJECT,object_id)
    except KeyError as e:fail(e,404)

@app.post("/api/analyze/cantilever/{object_id}")
def cantilever(object_id:str,force_n:float=100,length_mm:float|None=None,axis:str="x"):
    try:
        r=analysis.quick_cantilever(core.object_by_id(object_id),force_n,length_mm,axis);core.record_simulation("beam_screen",object_id,{"force_n":force_n,"length_mm":length_mm,"axis":axis},r);return r
    except Exception as e:fail(e)
@app.post("/api/analyze/fea/{object_id}")
def fea(object_id:str,force_n:float=100,support_axis:str="x",load_direction:str="z",resolution:int=10):
    try:
        r=analysis.linear_fea(core.object_by_id(object_id),force_n,support_axis,load_direction,resolution);core.record_simulation("linear_fea",object_id,{"force_n":force_n,"support_axis":support_axis,"load_direction":load_direction,"resolution":resolution},r);return r
    except Exception as e:fail(e)
@app.post("/api/analyze/modal/{object_id}")
def modal(object_id:str,support_axis:str="x",resolution:int=8,modes:int=6):
    try:
        r=analysis.modal_analysis(core.object_by_id(object_id),support_axis,resolution,modes);core.record_simulation("modal",object_id,{"support_axis":support_axis,"resolution":resolution,"modes":modes},r);return r
    except Exception as e:fail(e)
@app.post("/api/analyze/thermal/{object_id}")
def thermal(object_id:str,heat_w:float=10,ambient_c:float=22,h_w_m2k:float=8,resolution:int=14,fixed_axis:str|None=None,fixed_temp_c:float|None=None):
    try:
        r=analysis.thermal_analysis(core.object_by_id(object_id),heat_w,ambient_c,h_w_m2k,resolution,fixed_axis,fixed_temp_c);core.record_simulation("thermal",object_id,{"heat_w":heat_w,"ambient_c":ambient_c,"h_w_m2k":h_w_m2k},r);return r
    except Exception as e:fail(e)
@app.post("/api/optimize/{object_id}")
def optimize(object_id:str,body:OptimizeBody):
    try:return analysis.optimize_part(core.object_by_id(object_id),body.variables,body.objective,body.force_n,body.axis,body.deflection_max_mm,body.yield_fos_min,body.max_evals)
    except Exception as e:fail(e)
@app.post("/api/manufacturing/{object_id}")
def manufacturing(object_id:str,process:str="fdm"):
    try:return analysis.manufacturing_review(core.object_by_id(object_id),process)
    except Exception as e:fail(e)
@app.get("/api/system/capabilities")
def capabilities():return analysis.system_capabilities()|{"ollama":agents.status(),"component_count":components.registry_stats()["total"],"component_registry":components.registry_stats()}

@app.get("/api/agent/status")
def agent_status():return agents.status()
@app.post("/api/chat")
def chat(body:ChatMessage):
    try:
        if body.execute:
            plan=agents.plan_commands(body.text,body.model);results=[]
            for c in plan.get("commands",[]):results.append(core.execute(c["op"],c.get("args",{}),f"ollama:{body.model or 'qwen3:8b'}",body.text))
            return {"ok":True,"plan":plan,"results":len(results),"project":core.PROJECT}
        return {"ok":True,**agents.chat(body.text,body.model)}
    except Exception as e:fail(e,503)
@app.post("/api/agent")
def agent(body:AgentMessage):
    try:
        if body.role.lower()!="designer":return {"ok":True,**agents.review(body.text,body.model,body.role)}
        plan=agents.plan_commands(body.text,body.model);results=[]
        if body.execute:
            for c in plan.get("commands",[]):results.append(core.execute(c["op"],c.get("args",{}),f"ollama:{body.model or 'qwen3:8b'}",body.text))
        return {"ok":True,"plan":plan,"results":results,"project":core.PROJECT}
    except Exception as e:fail(e,503)

# Jarvis-facing local protocol. All routes remain loopback and token protected.
@app.get("/api/jarvis/status",dependencies=[])
def j_status(_:None=__import__('fastapi').Depends(require_jarvis)):
    return {"ok":True,"project":core.PROJECT.get("name"),"active_design":core.ACTIVE_DESIGN,"designs":core.list_branches(),"metrics":core.project_metrics(),"model":agents.DEFAULT_MODEL}
@app.get("/api/jarvis/summary")
def j_summary(_:None=__import__('fastapi').Depends(require_jarvis)):
    return {"project":core.PROJECT.get("name"),"active_design":core.ACTIVE_DESIGN,"objects":[{"id":o["id"],"name":o["name"],"kind":o["kind"],"component_ref":o.get("component_ref")} for o in core.PROJECT["objects"]],"requirements":core.requirement_checks(),"metrics":core.project_metrics()}
@app.get("/api/jarvis/designs")
def j_designs(_:None=__import__('fastapi').Depends(require_jarvis)):return core.list_branches()
@app.get("/api/jarvis/history")
def j_history(limit:int=30,_:None=__import__('fastapi').Depends(require_jarvis)):return list(reversed(core.PROJECT.get("ledger",[])[-limit:]))
@app.get("/api/jarvis/diff")
def j_diff(target:str,source:str|None=None,_:None=__import__('fastapi').Depends(require_jarvis)):return core.compare_branch(target,source)
@app.post("/api/jarvis/component-select")
def j_component(body:JarvisComponentBody,_:None=__import__('fastapi').Depends(require_jarvis)):return components.select_component(body.constraints,category=body.category,query=body.query,limit=10)
@app.get("/api/jarvis/reality-scan")
def j_reality(_:None=__import__('fastapi').Depends(require_jarvis)):
    scan=core.reality_check();risks=list(scan.get("risks",[]));stale=sum(1 for s in core.PROJECT.get("simulations",[]) if s.get("stale"))
    if stale:risks.append({"severity":"warning","code":"stale_analysis","message":f"{stale} prior analyses are stale after design changes."})
    if not any(d.get("physical_verified") for d in core.DESIGNS.values()):risks.append({"severity":"info","code":"no_physical_verification","message":"No design branch is marked physically verified."})
    return {**scan,"risks":risks,"stale_simulations":stale,"trust":"Component provenance and screening analyses do not replace physical verification."}
@app.post("/api/jarvis/analyze")
def j_analyze(body:JarvisAnalysisBody,_:None=__import__('fastapi').Depends(require_jarvis)):
    oid=body.object_id or (core.PROJECT["objects"][0]["id"] if core.PROJECT["objects"] else None)
    if not oid:raise HTTPException(400,"Project has no object to analyze")
    obj=core.object_by_id(oid);k=body.kind.lower();p=body.params
    if k in {"structural","fea"}:r=analysis.linear_fea(obj,**{x:p[x] for x in p if x in {"force_n","support_axis","load_direction","resolution"}})
    elif k=="modal":r=analysis.modal_analysis(obj,**p)
    elif k=="thermal":r=analysis.thermal_analysis(obj,**p)
    else:r=analysis.quick_cantilever(obj,**p)
    core.record_simulation(k,oid,p,r);return r
@app.post("/api/jarvis/change")
def j_change(body:JarvisChangeBody,_:None=__import__('fastapi').Depends(require_jarvis)):
    source=core.ACTIVE_DESIGN
    if body.always_branch:core.create_branch(f"jarvis-{__import__('datetime').datetime.now().strftime('%Y%m%d-%H%M%S')}",reason=body.text)
    plan=agents.plan_commands(body.text,body.model);n=0
    if body.execute:
        for c in plan.get("commands",[]):core.execute(c["op"],c.get("args",{}),f"jarvis:ollama:{body.model or agents.DEFAULT_MODEL}",body.text);n+=1
    return {"ok":True,"source_design":source,"new_design":core.ACTIVE_DESIGN,"plan":plan,"applied_commands":n,"requirements":core.requirement_checks(),"diff":core.compare_branch(source)}

@app.get("/api/tools")
def tools():return {"principle":"Human UI, local AI and Jarvis call the same deterministic typed operations; UI state is never authoritative.","operations":["add","add_component","replace_component","sync_component","update","transform","mate_components","connect_interfaces","disconnect","delete","add_feature","delete_feature","add_load","add_constraint","set_requirement","add_bom_item","add_note","code_write","code_delete","code_rename"],"component_registry":{"schema":"/api/components/schema","stats":"/api/components/stats","search":"POST /api/components/search","select":"POST /api/components/select","import_pack":"POST /api/components/import-pack","reality_check":"/api/reality-check","system_check":"/api/system-check"},"analysis":["cantilever screening","reduced-order structural preview","modal screening","thermal screening","parameter optimization","manufacturing screening"],"openapi":"/openapi.json","docs":"/docs"}
@app.get("/api/export/step/{object_id}")
def export_step(object_id:str):
    try:
        o=core.object_by_id(object_id);path=core.EXPORTS/f"{safe_name(o)}_{object_id[:8]}.step";cq.exporters.export(core.build_shape(o),str(path),exportType="STEP");return FileResponse(path,media_type="model/step",filename=f"{safe_name(o)}.step")
    except Exception as e:fail(e)
@app.get("/api/export/stl/{object_id}")
def export_stl(object_id:str):
    try:
        o=core.object_by_id(object_id);path=core.EXPORTS/f"{safe_name(o)}_{object_id[:8]}.stl";cq.exporters.export(core.build_shape(o),str(path),exportType="STL",tolerance=.08,angularTolerance=.15);return FileResponse(path,media_type="model/stl",filename=f"{safe_name(o)}.stl")
    except Exception as e:fail(e)

if __name__=="__main__":
    import uvicorn;uvicorn.run(app,host="127.0.0.1",port=8765,log_level="warning")
