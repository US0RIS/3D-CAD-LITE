from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

from core import MATERIALS, PROJECT, requirement_checks
from analysis import system_capabilities

OLLAMA = "http://127.0.0.1:11434"


def status() -> dict[str, Any]:
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=1.5) as r:
            data = json.loads(r.read().decode())
        return {"ollama": True, "models": [m.get("name") for m in data.get("models", [])]}
    except Exception:
        return {"ollama": False, "models": []}


def _chat(model: str, system: str, user: str, json_mode: bool = False, timeout: int = 90) -> str:
    payload: dict[str, Any] = {"model": model, "stream": False, "messages": [{"role":"system","content":system},{"role":"user","content":user}], "options": {"temperature": 0.15}}
    if json_mode: payload["format"] = "json"
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        response = json.loads(r.read().decode())
    return response.get("message", {}).get("content", "")


def compact_state() -> dict[str, Any]:
    return {
        "project": {"name":PROJECT["name"],"units":PROJECT["units"],"active_branch":PROJECT.get("active_branch"),"settings":PROJECT.get("settings",{})},
        "objects": [{"id":o["id"],"name":o["name"],"kind":o["kind"],"params":o.get("params"),"material":o.get("material"),"transform":o.get("transform"),"semantic":o.get("semantic"),"features":o.get("features",[])} for o in PROJECT.get("objects",[])],
        "joints": PROJECT.get("joints",[]), "loads":PROJECT.get("loads",[]), "constraints":PROJECT.get("constraints",[]),
        "requirements": requirement_checks(), "bom":PROJECT.get("bom",[]), "recent_simulations":PROJECT.get("simulations",[])[-6:],
        "materials": list(MATERIALS.keys()), "capabilities":system_capabilities(),
    }


COMMAND_SCHEMA = r"""
Return ONLY JSON in the form {"commands":[...],"summary":"...","assumptions":[...]}. Do not return Markdown.
Allowed deterministic commands:
- add: {kind:box|cylinder|sphere|extrude|revolve, name?, x?,y?,z?, radius?,height?, depth?, profile?, position?, material?}
  extrude profile examples: {"type":"rectangle","width":50,"height":30}, {"type":"circle","radius":10}, {"type":"polygon","points":[[x,y],...]}
  revolve profile: {"type":"polygon","points":[[radius,z],...]}, plus angle.
- update: {id, name?, material?, params?, appearance?, physical?, semantic?, manufacturing?}
- transform: {id, position?, rotation?, scale?}; position mm, rotation degrees.
- add_feature: {id, feature:{type:hole|pocket_circle|pocket_rect|fillet_all|chamfer_all,...}}
  hole: diameter,x,y,z,axis; pocket_circle:diameter,depth,x,y,z,axis; pocket_rect:width,height,depth,x,y,z,axis; fillet_all:radius; chamfer_all:distance.
- delete_feature: {id, feature_id}
- delete: {id} or {ids:[...]}
- add_joint: {parent_id,child_id,type:fixed|revolute|prismatic|spherical|spring,name?,anchor_parent?,anchor_child?,axis?,limits?,motor?,spring?}
- update_joint: {id,...}; delete_joint:{id}
- add_load: {object_id,name?,type:force|torque|heat,vector?,face?,value?}; add_constraint:{object_id,name?,type:fixed|temperature,face?,value?}
- set_requirement: {metric,operator,value,unit?,name?}; metrics include mass_kg,cost_usd,parts,volume_mm3,max_displacement_mm,yield_fos,max_temperature_c,first_mode_hz.
- add_bom_item: {name,part_number?,supplier?,qty?,unit_cost?,mass_kg?,url?,linked_object_id?,notes?}
- add_note: {type:note|decision|experiment|calculation,title,body,evidence?}
- project_name:{name}; settings:{gravity?,grid?,ollama_model?}
Rules: Never invent IDs; use only IDs from STATE. Prefer semantic roles and named features. Make small reversible changes. Do not claim a simulation ran unless STATE contains its result. Do not use arbitrary Python or shell commands.
"""


def plan_commands(text: str, model: str) -> dict[str, Any]:
    system = "You are ForgeCAD's mechanical design agent. Convert an engineering design request into safe typed CAD/engineering commands. Think about geometry, physical plausibility, requirements, and reversibility. " + COMMAND_SCHEMA
    raw = _chat(model, system, "STATE="+json.dumps(compact_state(),separators=(",",":"))+"\nREQUEST="+text, json_mode=True)
    data = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I|re.S))
    if isinstance(data, list): data={"commands":data,"summary":"","assumptions":[]}
    if not isinstance(data,dict) or not isinstance(data.get("commands"),list): raise ValueError("Agent did not return a valid command plan")
    data["commands"] = data["commands"][:24]
    return data


def review(text: str, model: str, role: str = "verifier") -> dict[str, Any]:
    role = role.lower()
    if role == "analyst":
        sys = "You are ForgeCAD's analysis engineer. Inspect the supplied canonical project state and simulation history. Identify the analyses that are justified, important missing boundary conditions, likely failure modes, and the next highest-information engineering test. Do not fabricate numeric results. Return concise technical prose."
    elif role == "optimizer":
        sys = "You are ForgeCAD's optimization engineer. Inspect requirements, geometry parameters, material choices, simulations, and BOM. Recommend concrete design variables, bounds, objectives, constraints, and a verification sequence. Do not pretend an optimization has run unless results are present. Return concise technical prose."
    else:
        sys = "You are ForgeCAD's independent verification engineer. You did not design this project. Try to invalidate the design or simulation conclusions. Check assumptions, boundary conditions, load cases, mesh convergence, material data, safety factors, thermal/contact effects, tolerances, manufacturability, and requirement coverage. Separate observed facts from concerns. Do not fabricate numeric results. Return concise technical prose."
    raw = _chat(model, sys, "STATE="+json.dumps(compact_state(),separators=(",",":"))+"\nUSER_FOCUS="+text, json_mode=False)
    return {"role": role, "text": raw}
