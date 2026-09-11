from __future__ import annotations
import json, os, re, urllib.request
from typing import Any

DEFAULT_MODEL=os.environ.get("FORGECAD_OLLAMA_MODEL","qwen3:8b")
OPS=["add","add_component","replace_component","sync_component","update","transform","mate_components","connect_interfaces","disconnect","delete","add_feature","delete_feature","add_load","add_constraint","set_requirement","add_bom_item","add_note","code_write","code_delete","code_rename","project_name","settings"]

def _request(path:str,payload:dict[str,Any]|None=None,timeout=90):
    url="http://127.0.0.1:11434"+path; data=None if payload is None else json.dumps(payload).encode(); req=urllib.request.Request(url,data=data,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode())
def status():
    try:
        d=_request("/api/tags",None,2);models=[x.get("name") or x.get("model") for x in d.get("models",[])];return {"available":True,"models":models,"configured":DEFAULT_MODEL,"configured_present":any(str(x).split(":")[0]==DEFAULT_MODEL.split(":")[0] for x in models)}
    except Exception as e:return {"available":False,"models":[],"configured":DEFAULT_MODEL,"error":str(e)}
def _json_from(text:str):
    text=text.strip()
    try:return json.loads(text)
    except Exception:pass
    m=re.search(r"```(?:json)?\s*(\{.*?\})\s*```",text,re.S)
    if m:
        try:return json.loads(m.group(1))
        except Exception:pass
    a=text.find("{");b=text.rfind("}")
    if a>=0 and b>a:return json.loads(text[a:b+1])
    raise ValueError("Agent did not return valid JSON")

_STOP={"the","and","for","with","from","into","onto","that","this","then","than","make","build","add","put","use","using","need","want","please","component","part","parts","real","world","design","project","some","have","should","would","could","can","our","its","like"}
_CATEGORY_MAP={"stepper":"stepper_motor","motor":"stepper_motor","servo":"servo","solenoid":"solenoid","bearing":"bearing","fan":"fan","raspberry":"compute","pi":"compute","arduino":"microcontroller","microcontroller":"microcontroller","sensor":"sensor","battery":"battery","fastener":"fastener","screw":"fastener","bolt":"fastener","linear":"linear_motion","rail":"linear_motion","buck":"power","regulator":"power","supply":"power_supply","driver":"motor_driver"}

def _candidate_pool(text:str,component_registry,limit:int=28):
    """Broad candidate retrieval for the local planner.

    Conversational requests are poor exact registry queries. Search significant terms
    independently, add category-directed candidates, then rerank exact manufacturer/model
    matches, trust, and CAD fidelity. This makes a named real part much less likely to be
    displaced by an alphabetically nearby generic proxy.
    """
    low=text.lower()
    raw=[t for t in re.findall(r"[a-z0-9][a-z0-9_.+-]*",low) if len(t)>=2]
    tokens=[]
    for t in raw:
        if t not in _STOP and t not in tokens:tokens.append(t)
    # Preserve likely model identifiers even when short (e.g. Pi 5, M3, 608).
    ids=[t for t in raw if any(ch.isdigit() for ch in t)]
    queries=[]
    for t in [*ids,*tokens]:
        if t not in queries:queries.append(t)
    rows={}
    def add(c,origin_bonus=0):
        cid=c.get("id")
        if not cid:return
        blob=" ".join(str(c.get(k,"")) for k in ("id","manufacturer","model","name","manufacturer_part_number")).lower()
        exact=sum(1 for q in queries if q and q in blob)
        generic_penalty=12 if str(c.get("manufacturer","")).lower()=="generic" else 0
        geom=component_registry.GEOMETRY_RANK.get(str(c.get("geometry",{}).get("fidelity","none")),0)
        trust=int(c.get("trust_score",0))
        asset_bonus=8 if any(a.get("role")=="geometry" for a in c.get("geometry",{}).get("assets",[])) else 0
        score=origin_bonus+exact*16+trust*.10+geom*.12+asset_bonus-generic_penalty
        old=rows.get(cid)
        if old is None or score>old[0]:rows[cid]=(score,c)
    for q in queries[:10]:
        try:
            for c in component_registry.search_components(q,limit=8,include_infeasible=True)["results"]:add(c,8)
        except Exception:pass
    cats=[]
    for token,cat in _CATEGORY_MAP.items():
        if token in raw or token in low.split():
            if cat not in cats:cats.append(cat)
    for cat in cats:
        try:
            for c in component_registry.search_components("",cat,limit=10,include_infeasible=True)["results"]:add(c,4)
        except Exception:pass
    ranked=sorted(rows.values(),key=lambda x:(-x[0],str(x[1].get("name",""))))[:limit]
    out=[]
    for score,c in ranked:
        g=c.get("geometry",{});p=c.get("procurement",{});prov=c.get("provenance") or []
        out.append({
            "id":c.get("id"),"name":c.get("name"),"manufacturer":c.get("manufacturer"),"model":c.get("model"),
            "mpn":c.get("manufacturer_part_number"),"category":c.get("category"),"dimensions_mm":c.get("dimensions_mm"),"mass_g":c.get("mass_g"),
            "specs":c.get("specs",{}),"interfaces":[i.get("id") for i in c.get("interfaces",[])],
            "geometry_fidelity":g.get("fidelity"),"geometry_assets":len(g.get("assets",[])),"trust_score":c.get("trust_score"),
            "supplier":p.get("supplier"),"supplier_sku":p.get("sku"),"source":prov[0].get("url") if prov else None,
            "retrieval_score":round(score,2),
        })
    return out

def plan_commands(text:str,model:str|None=None,project:dict[str,Any]|None=None):
    import core
    import component_registry
    m=model or DEFAULT_MODEL;p=project or core.PROJECT
    summary={"name":p.get("name"),"objects":[{"id":o.get("id"),"name":o.get("name"),"kind":o.get("kind"),"params":o.get("params"),"material":o.get("material"),"component_ref":o.get("component_ref"),"geometry_fidelity":o.get("component_snapshot",{}).get("geometry",{}).get("fidelity"),"interfaces":[i.get("id") for i in o.get("interfaces",[])]} for o in p.get("objects",[])],"requirements":p.get("requirements",[])[:20],"connections":p.get("connections",[])[:30]}
    candidates=_candidate_pool(text,component_registry)
    system=f"""You are ForgeCAD's local mechanical/electromechanical design planner. Return JSON only: {{\"summary\":\"...\",\"commands\":[{{\"op\":\"...\",\"args\":{{...}}}}],\"checks\":[\"...\"]}}. Allowed operations: {OPS}.

Purchased-hardware rules are strict:
- Never invent object IDs, manufacturer part numbers, or component IDs.
- For commercially purchasable hardware, use add_component only with an exact component_id from COMPONENT CANDIDATES.
- If the user names a manufacturer/model and that exact item is absent, do NOT substitute a generic lookalike. Return no purchase command and state that the exact catalog/CAD entry is missing.
- A Generic component or geometry below detailed_parametric fidelity is conceptual/proxy data, not a final real-world selection. Use it only when the user explicitly asks for a conceptual placeholder.
- Prefer manufacturer-sourced candidates, real geometry assets, higher geometry fidelity, and higher trust when engineering requirements are otherwise comparable.
- Preserve purchased geometry and frozen component snapshots. Never stretch, drill, or edit a purchased component as fabricated stock; make a separate bracket/adapter instead.
- Use mate_components only with exact object IDs/interface IDs supplied in project state. Use connect_interfaces for electrical/logical connections.
- If candidate data is insufficient to verify fit, voltage/current, force/torque, or mounting, say which data is missing rather than assuming it.

For fabricated geometry, prefer explicit dimensions in mm. Do not claim a screening calculation proves a safety-critical design."""
    summary["component_candidates"]=candidates
    resp=_request("/api/chat",{"model":m,"stream":False,"messages":[{"role":"system","content":system},{"role":"user","content":f"PROJECT:\n{json.dumps(summary)}\n\nREQUEST:\n{text}"}],"options":{"temperature":0.12}},120)
    out=_json_from(resp.get("message",{}).get("content",resp.get("response","")));out.setdefault("commands",[])
    valid_ids={c["id"] for c in candidates}
    for c in out["commands"]:
        if c.get("op") not in OPS:raise ValueError(f"Agent proposed unsupported operation: {c.get('op')}")
        if c.get("op") in {"add_component","replace_component"}:
            cid=str(c.get("args",{}).get("component_id") or c.get("args",{}).get("new_component_id") or "")
            if cid not in valid_ids:raise ValueError(f"Agent proposed component not present in its verified candidate set: {cid}")
            definition=component_registry.component_by_id(cid);fidelity=str(definition.get("geometry",{}).get("fidelity","none"));rank=component_registry.GEOMETRY_RANK.get(fidelity,0)
            if str(definition.get("manufacturer","")).lower()=="generic" or rank<component_registry.GEOMETRY_RANK["detailed_parametric"]:
                conceptual=any(x in text.lower() for x in ("placeholder","concept","conceptual","rough","temporary","mockup"))
                if not conceptual:raise ValueError(f"Agent refused non-final proxy component {cid} ({fidelity}); import/select a real component instead")
    return out
def review(text:str,model:str|None=None,role:str="verifier"):
    import core
    m=model or DEFAULT_MODEL; system=f"You are ForgeCAD's independent {role}. Review engineering assumptions, loads, constraints, materials, manufacturability and validation gaps. Be concise and distinguish known facts from screening estimates."
    resp=_request("/api/chat",{"model":m,"stream":False,"messages":[{"role":"system","content":system},{"role":"user","content":text+"\n\nProject metrics: "+json.dumps(core.project_metrics())}]},120)
    return {"role":role,"model":m,"text":resp.get("message",{}).get("content",resp.get("response",""))}
def chat(text:str,model:str|None=None):
    import core
    m=model or DEFAULT_MODEL; system="You are ForgeCAD, an engineering copilot. Answer about the current design. When the user requests a change, describe the intended operation and recommend using Apply if execution is desired. Treat purchased-part geometry fidelity and source trust as engineering facts; never describe a proxy envelope as the real physical part. Never overstate screening solver fidelity."
    resp=_request("/api/chat",{"model":m,"stream":False,"messages":[{"role":"system","content":system},{"role":"user","content":text+"\n\nCurrent design: "+json.dumps({"name":core.PROJECT.get('name'),"metrics":core.project_metrics(),"objects":[{"name":o.get('name'),"component_ref":o.get('component_ref'),"fidelity":o.get('component_snapshot',{}).get('geometry',{}).get('fidelity')} for o in core.PROJECT.get('objects',[])]})}]},120)
    return {"model":m,"text":resp.get("message",{}).get("content",resp.get("response",""))}
