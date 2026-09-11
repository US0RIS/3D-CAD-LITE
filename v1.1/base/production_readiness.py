from __future__ import annotations

"""Production-readiness assessment for ForgeCAD designs.

This is intentionally stricter than the ordinary reality check. A design can be
useful while it still contains proxy geometry, unresolved component provenance,
or open engineering issues; it must not, however, be presented as ready for a
real-world verification baseline until those conditions are resolved.

Passing this gate is *not* proof that a design works or is safe. It only means the
ForgeCAD model has enough physical authority to be eligible for the user's later
"works in real life" attestation.
"""

from copy import deepcopy
from typing import Any, Callable

import assembly_validation
import component_registry
import physical_components
import system_validation

MIN_FINAL_GEOMETRY_RANK = component_registry.GEOMETRY_RANK["detailed_parametric"]
MIN_FINAL_TRUST = component_registry.TRUST_RANK["forgecad_derived"]


def _risk(severity: str, code: str, message: str, **extra) -> dict[str, Any]:
    return {"severity": severity, "code": code, "message": message, **extra}


def assess(project: dict[str, Any], shape_builder: Callable[[dict[str, Any]], Any]) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    component_rows: list[dict[str, Any]] = []

    for obj in project.get("objects", []):
        if obj.get("kind") != "component":
            continue
        cid = str(obj.get("component_ref") or "")
        snapshot = obj.get("component_snapshot") if isinstance(obj.get("component_snapshot"), dict) else {}
        try:
            live = component_registry.component_by_id(cid)
        except KeyError:
            live = snapshot
        c = live or snapshot
        manufacturer = str(c.get("manufacturer") or "Unknown")
        geometry = c.get("geometry") or {}
        fidelity = str(geometry.get("fidelity") or "none")
        rank = component_registry.GEOMETRY_RANK.get(fidelity, 0)
        trust = int(c.get("trust_score") or 0)
        assets = [a for a in geometry.get("assets", []) if a.get("role") == "geometry"]
        resolved_assets = [a for a in assets if component_registry.resolve_asset_path(a) is not None]

        row = {
            "object_id": obj.get("id"),
            "component_id": cid,
            "name": obj.get("name") or c.get("name"),
            "manufacturer": manufacturer,
            "geometry_fidelity": fidelity,
            "trust_score": trust,
            "geometry_assets": len(assets),
            "resolved_geometry_assets": len(resolved_assets),
        }
        component_rows.append(row)

        if not cid or not c:
            blockers.append(_risk("error", "component_identity_missing", f"{obj.get('name','Component')} has no authoritative registry identity.", object_id=obj.get("id")))
            continue
        if manufacturer.lower() == "generic":
            blockers.append(_risk("error", "generic_component_proxy", f"{obj.get('name')} is a generic proxy, not a specific purchased part.", object_id=obj.get("id"), component_id=cid))
        if rank < MIN_FINAL_GEOMETRY_RANK:
            blockers.append(_risk("error", "geometry_not_final", f"{obj.get('name')} uses {fidelity} geometry; final physical baselines require detailed parametric or validated CAD geometry.", object_id=obj.get("id"), component_id=cid))
        if trust < MIN_FINAL_TRUST:
            blockers.append(_risk("error", "component_provenance_too_weak", f"{obj.get('name')} has source trust {trust}/100; provenance is too weak for a physical baseline.", object_id=obj.get("id"), component_id=cid))
        if geometry.get("official_asset_expected") and not resolved_assets:
            blockers.append(_risk("error", "manufacturer_cad_missing", f"{obj.get('name')} expects manufacturer CAD, but that CAD asset is not available in this build/project.", object_id=obj.get("id"), component_id=cid))
        if fidelity in {"official_step", "official_cad", "verified_step"} and assets and not resolved_assets:
            blockers.append(_risk("error", "cad_asset_unresolved", f"{obj.get('name')} claims {fidelity} geometry but its registered CAD asset cannot be resolved.", object_id=obj.get("id"), component_id=cid))

    system = system_validation.validate_system(project)
    for r in system.get("risks", []):
        target = blockers if r.get("severity") == "error" else warnings
        target.append(deepcopy(r))

    try:
        assembly = assembly_validation.validate_assembly(project, shape_builder, min_clearance_mm=1.0)
        for r in assembly.get("risks", []):
            target = blockers if r.get("severity") == "error" else warnings
            target.append(deepcopy(r))
    except Exception as exc:
        assembly = {"ok": False, "counts": {"error": 1, "warning": 0, "info": 0}, "risks": []}
        blockers.append(_risk("error", "assembly_validation_unavailable", f"Physical assembly validation failed to run: {exc}"))

    # Deduplicate exact code/object combinations when system and assembly checks surface
    # the same underlying issue.
    deduped: list[dict[str, Any]] = []
    seen = set()
    for r in blockers:
        key = (r.get("code"), r.get("object_id"), r.get("component_id"), r.get("message"))
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    blockers = deduped

    return {
        "ready_for_physical_verification": len(blockers) == 0,
        "blockers": blockers,
        "warnings": warnings,
        "counts": {"blockers": len(blockers), "warnings": len(warnings)},
        "components": component_rows,
        "system": system,
        "assembly": assembly,
        "disclaimer": "Passing this gate does not prove safety or real-world function; it only qualifies the model for physical verification.",
    }
