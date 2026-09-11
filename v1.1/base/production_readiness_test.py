from __future__ import annotations

import acceptance_design
import component_registry
import core
import production_readiness


project = core.upgrade_project(acceptance_design.build_project())
report = production_readiness.assess(project, core.build_shape)
if not report["ready_for_physical_verification"]:
    raise SystemExit(f"Acceptance design unexpectedly failed production-readiness gate: {report['blockers']}")

# A generic envelope can still be used for conceptual layout, but the same project
# must immediately become ineligible for a physical-verification baseline.
generic = next(
    c for c in component_registry.all_components()
    if c.get("manufacturer") == "Generic" and component_registry.GEOMETRY_RANK.get(c.get("geometry", {}).get("fidelity", "none"), 0) < component_registry.GEOMETRY_RANK["detailed_parametric"]
)
proxy = component_registry.make_project_object(generic["id"])
proxy["id"] = "readiness-proxy-regression"
project["objects"].append(proxy)
project.setdefault("bom", []).append(component_registry.bom_item(generic["id"], 1))
blocked = production_readiness.assess(project, core.build_shape)
if blocked["ready_for_physical_verification"]:
    raise SystemExit("Production-readiness gate allowed a generic proxy component")
codes = {r.get("code") for r in blocked["blockers"]}
if "generic_component_proxy" not in codes and "geometry_not_final" not in codes:
    raise SystemExit(f"Proxy project failed for the wrong reason: {blocked['blockers']}")

print("ForgeCAD production readiness gate: PASS")
