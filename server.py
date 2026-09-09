from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import cadquery as cq
from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import agents
import analysis
import core

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"


class Command(BaseModel):
    op: str
    args: dict[str, Any] = Field(default_factory=dict)
    actor: str = "human"
    reason: str = ""


class AgentMessage(BaseModel):
    text: str
    model: str | None = None
    role: str = "designer"
    execute: bool = True


class WorkflowMessage(BaseModel):
    text: str
    designer_model: str | None = None
    verifier_model: str | None = None
    execute: bool = True


class OptimizeBody(BaseModel):
    variables: list[dict[str, Any]]
    objective: str = "mass"
    force_n: float = 100.0
    axis: str = "x"
    deflection_max_mm: float | None = None
    yield_fos_min: float | None = None
    max_evals: int = 90


app = FastAPI(
    title="ForgeCAD Engineering API",
    version="1.0.0",
    description="AI-native local CAD/CAE workbench. Humans and agents manipulate the same canonical project model through typed operations.",
)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def fail(e: Exception, status: int = 400):
    raise HTTPException(status, str(e))


@app.get("/")
def root():
    return FileResponse(STATIC / "index.html")


@app.get("/api/project")
def get_project():
    return core.PROJECT


@app.post("/api/project/reset")
def reset_project():
    return core.reset_project()


@app.post("/api/project/import-json")
def import_project_json(payload: dict[str, Any] = Body(...)):
    try:
        state = core.upgrade_project(payload)
        core.PROJECT.clear(); core.PROJECT.update(state)
        core.HISTORY[:] = [deepcopy(core.PROJECT)]; core.REDO[:] = []
        core.push_history("import project JSON", "human", "replace canonical project state")
        return core.PROJECT
    except Exception as e:
        fail(e)


@app.post("/api/import/step")
async def import_step(file: UploadFile = File(...)):
    try:
        data = await file.read()
        if len(data) > 100 * 1024 * 1024:
            raise ValueError("STEP file exceeds 100 MB")
        obj = core.import_step_bytes(file.filename or "import.step", data)
        return {"ok": True, "object": obj}
    except Exception as e:
        fail(e)


@app.post("/api/command")
def command(cmd: Command):
    try:
        return core.execute(cmd.op, cmd.args, cmd.actor, cmd.reason)
    except KeyError as e:
        fail(e, 404)
    except Exception as e:
        fail(e)


@app.post("/api/undo")
def undo():
    return {"ok": core.undo(), "project": core.PROJECT}


@app.post("/api/redo")
def redo():
    return {"ok": core.redo(), "project": core.PROJECT}


@app.get("/api/materials")
def materials():
    return core.MATERIALS


@app.get("/api/mesh/{object_id}")
def mesh(object_id: str, tolerance: float = 0.35):
    try:
        return core.tessellate(core.object_by_id(object_id), tolerance)
    except KeyError as e:
        fail(e, 404)
    except Exception as e:
        fail(e)


@app.get("/api/metrics")
def metrics():
    try:
        per = {o["id"]: core.object_metrics(o) for o in core.PROJECT["objects"]}
        return {"project": core.project_metrics(), "objects": per}
    except Exception as e:
        fail(e)


@app.get("/api/requirements/check")
def requirements_check():
    try:
        return core.requirement_checks()
    except Exception as e:
        fail(e)


@app.post("/api/analyze/cantilever/{object_id}")
def cantilever(object_id: str, force_n: float = 100.0, length_mm: float | None = None, axis: str = "x"):
    try:
        result = analysis.quick_cantilever(core.object_by_id(object_id), force_n, length_mm, axis)
        core.record_simulation("beam_screen", object_id, {"force_n":force_n,"length_mm":length_mm,"axis":axis}, result)
        return result
    except Exception as e:
        fail(e)


@app.post("/api/analyze/fea/{object_id}")
def fea(object_id: str, force_n: float = 100.0, support_axis: str = "x", load_direction: str = "z", resolution: int = 10):
    try:
        result = analysis.linear_fea(core.object_by_id(object_id), force_n, support_axis, load_direction, resolution)
        core.record_simulation("linear_fea", object_id, {"force_n":force_n,"support_axis":support_axis,"load_direction":load_direction,"resolution":resolution}, result)
        return result
    except Exception as e:
        fail(e)


@app.post("/api/analyze/modal/{object_id}")
def modal(object_id: str, support_axis: str = "x", resolution: int = 8, modes: int = 6):
    try:
        result = analysis.modal_analysis(core.object_by_id(object_id), support_axis, resolution, modes)
        core.record_simulation("modal", object_id, {"support_axis":support_axis,"resolution":resolution,"modes":modes}, result)
        return result
    except Exception as e:
        fail(e)


@app.post("/api/analyze/thermal/{object_id}")
def thermal(object_id: str, heat_w: float = 10.0, ambient_c: float = 22.0, h_w_m2k: float = 8.0, resolution: int = 14, fixed_axis: str | None = None, fixed_temp_c: float | None = None):
    try:
        result = analysis.thermal_analysis(core.object_by_id(object_id), heat_w, ambient_c, h_w_m2k, resolution, fixed_axis, fixed_temp_c)
        core.record_simulation("thermal", object_id, {"heat_w":heat_w,"ambient_c":ambient_c,"h_w_m2k":h_w_m2k,"resolution":resolution,"fixed_axis":fixed_axis,"fixed_temp_c":fixed_temp_c}, result)
        return result
    except Exception as e:
        fail(e)


@app.post("/api/optimize/{object_id}")
def optimize(object_id: str, body: OptimizeBody):
    try:
        result = analysis.optimize_part(core.object_by_id(object_id), body.variables, body.objective, body.force_n, body.axis, body.deflection_max_mm, body.yield_fos_min, body.max_evals)
        core.record_simulation("parameter_optimization", object_id, body.model_dump(), {"mass_kg":result["best"]["mass_kg"], "score":result["best"]["mass_kg"]})
        return result
    except Exception as e:
        fail(e)


@app.post("/api/manufacturing/{object_id}")
def manufacturing(object_id: str, process: str = "fdm"):
    try:
        return analysis.manufacturing_review(core.object_by_id(object_id), process)
    except Exception as e:
        fail(e)


@app.get("/api/system/capabilities")
def capabilities():
    data = analysis.system_capabilities()
    data["ollama"] = agents.status()
    return data


@app.get("/api/branches")
def branches():
    return core.list_branches()


@app.post("/api/branch")
def branch(cmd: Command):
    try:
        return {"ok": True, "project": core.create_branch(str(cmd.args.get("name", "branch")))}
    except Exception as e:
        fail(e)


@app.post("/api/branch/switch")
def switch_branch(cmd: Command):
    try:
        return {"ok": True, "project": core.switch_branch(str(cmd.args.get("name", "main")))}
    except KeyError as e:
        fail(e, 404)
    except Exception as e:
        fail(e)


@app.get("/api/branch/compare/{name}")
def compare_branch(name: str):
    try:
        return core.compare_branch(name)
    except KeyError as e:
        fail(e, 404)
    except Exception as e:
        fail(e)


@app.get("/api/agent/status")
def agent_status():
    return agents.status()


@app.post("/api/agent")
def agent(msg: AgentMessage):
    model = msg.model or core.PROJECT.get("settings", {}).get("ollama_model", "qwen3:8b")
    role = msg.role.lower()
    try:
        if role == "designer":
            plan = agents.plan_commands(msg.text, model)
            results = []
            if msg.execute:
                for c in plan["commands"]:
                    if not isinstance(c, dict) or "op" not in c: continue
                    results.append(core.execute(str(c["op"]), c.get("args", {}), f"ollama:{model}:designer", msg.text))
            return {"ok": True, "role": role, "plan": plan, "results": results, "project": core.PROJECT}
        review = agents.review(msg.text, model, role)
        return {"ok": True, **review}
    except Exception as e:
        fail(e, 503)


@app.post("/api/agent/workflow")
def agent_workflow(msg: WorkflowMessage):
    designer = msg.designer_model or core.PROJECT.get("settings", {}).get("ollama_model", "qwen3:8b")
    verifier = msg.verifier_model or designer
    try:
        plan = agents.plan_commands(msg.text, designer)
        results = []
        if msg.execute:
            for c in plan["commands"]:
                if not isinstance(c, dict) or "op" not in c: continue
                results.append(core.execute(str(c["op"]), c.get("args", {}), f"ollama:{designer}:designer", msg.text))
        critique = agents.review("Verify the design changes made for this request: " + msg.text, verifier, "verifier")
        return {"ok": True, "plan": plan, "results": results, "verification": critique, "project": core.PROJECT}
    except Exception as e:
        fail(e, 503)


@app.get("/api/tools")
def tools():
    return {
        "principle": "Human UI and AI agents call the same deterministic engineering operations; GUI state is never authoritative.",
        "operations": [
            "add", "update", "transform", "delete", "add_feature", "delete_feature", "add_joint", "update_joint", "delete_joint",
            "add_load", "delete_load", "add_constraint", "delete_constraint", "set_requirement", "delete_requirement",
            "add_bom_item", "update_bom_item", "delete_bom_item", "add_note", "project_name", "settings"
        ],
        "analysis": ["cantilever screening", "linear static FEA preview", "modal preview", "thermal preview", "parameter optimization", "manufacturing screening"],
        "openapi": "/openapi.json", "docs": "/docs",
    }


@app.get("/api/export")
def export_project():
    return core.PROJECT


def safe_name(obj: dict[str, Any]) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", obj.get("name", "part")).strip("_") or "part"


@app.get("/api/export/step/{object_id}")
def export_step(object_id: str):
    try:
        obj = core.object_by_id(object_id); safe = safe_name(obj); path = core.EXPORTS / f"{safe}_{object_id[:8]}.step"
        cq.exporters.export(core.build_shape(obj), str(path), exportType="STEP")
        return FileResponse(path, media_type="model/step", filename=f"{safe}.step")
    except Exception as e:
        fail(e)


@app.get("/api/export/stl/{object_id}")
def export_stl(object_id: str):
    try:
        obj = core.object_by_id(object_id); safe = safe_name(obj); path = core.EXPORTS / f"{safe}_{object_id[:8]}.stl"
        cq.exporters.export(core.build_shape(obj), str(path), exportType="STL", tolerance=0.05, angularTolerance=0.1)
        return FileResponse(path, media_type="model/stl", filename=f"{safe}.stl")
    except Exception as e:
        fail(e)


if __name__ == "__main__":
    import uvicorn
    print("ForgeCAD Engineering Workbench: http://127.0.0.1:8765")
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
