from __future__ import annotations

import math
import os
import platform
import shutil
from copy import deepcopy
from typing import Any

import numpy as np
from scipy.optimize import differential_evolution
from scipy.sparse import coo_matrix, csr_matrix, diags
from scipy.sparse.linalg import eigsh, spsolve

from core import MATERIALS, PROJECT, build_shape, object_metrics, project_metrics

AXIS = {"x": 0, "y": 1, "z": 2}


def quick_cantilever(obj: dict[str, Any], force_n: float, length_mm: float | None = None, axis: str = "x") -> dict[str, Any]:
    if axis not in AXIS:
        raise ValueError("axis must be x, y, or z")
    m = MATERIALS.get(obj.get("material"), MATERIALS["Aluminum 6061-T6"])
    shape = build_shape(obj)
    bb = shape.BoundingBox()
    scale = obj.get("transform", {}).get("scale", [1, 1, 1])
    dims = {"x": bb.xlen * abs(float(scale[0])), "y": bb.ylen * abs(float(scale[1])), "z": bb.zlen * abs(float(scale[2]))}
    Lmm = float(length_mm or dims[axis])
    transverse = [d for k, d in dims.items() if k != axis]
    b_mm, h_mm = sorted(transverse, reverse=True)
    I = (b_mm / 1000.0) * (h_mm / 1000.0) ** 3 / 12.0
    L = Lmm / 1000.0
    E = float(m["youngs_modulus"])
    F = float(force_n)
    delta = F * L**3 / (3 * E * I) if I > 0 else float("inf")
    sigma = (F * L) * (h_mm / 2000.0) / I if I > 0 else float("inf")
    fos = float(m["yield_strength"]) / sigma if sigma > 0 else float("inf")
    return {
        "method": "cantilever bounding-section approximation", "force_n": F, "length_mm": Lmm,
        "deflection_mm": delta * 1000, "max_bending_stress_mpa": sigma / 1e6, "yield_fos": fos,
        "warnings": ["Screening calculation only; not finite-element analysis.", "Uses the part bounding box as an equivalent solid rectangular section; holes and fillets are not reflected in section inertia."],
    }


def voxel_tet_mesh(obj: dict[str, Any], resolution: int = 10) -> dict[str, Any]:
    resolution = max(4, min(int(resolution), 22))
    shape = build_shape(obj)
    bb = shape.BoundingBox()
    mins = np.array([bb.xmin, bb.ymin, bb.zmin], dtype=float)
    maxs = np.array([bb.xmax, bb.ymax, bb.zmax], dtype=float)
    dims = np.maximum(maxs - mins, 1e-6)
    scale_vec = np.abs(np.asarray(obj.get("transform", {}).get("scale", [1, 1, 1]), dtype=float))
    physical_dims = np.maximum(dims * scale_vec, 1e-6)
    longest = float(physical_dims.max())
    cells = np.maximum(3, np.round(resolution * physical_dims / longest).astype(int))
    cells = np.minimum(cells, resolution)
    xs = [np.linspace(mins[i], maxs[i], cells[i] + 1) for i in range(3)]
    node_index: dict[tuple[int, int, int], int] = {}
    nodes_mm: list[list[float]] = []
    tets: list[tuple[int, int, int, int]] = []
    occupied_cells: list[tuple[int, int, int]] = []
    tetA = [(0,1,3,4),(1,2,3,6),(1,4,5,6),(3,4,6,7),(1,3,4,6)]
    tetB = [(0,1,2,5),(0,2,3,7),(0,4,5,7),(2,5,6,7),(0,2,5,7)]
    corners = [(0,0,0),(1,0,0),(1,1,0),(0,1,0),(0,0,1),(1,0,1),(1,1,1),(0,1,1)]

    def get_node(i: int, j: int, k: int) -> int:
        key = (i,j,k)
        if key not in node_index:
            node_index[key] = len(nodes_mm)
            nodes_mm.append([float(xs[0][i]), float(xs[1][j]), float(xs[2][k])])
        return node_index[key]

    tol = max(1e-7, longest * 1e-8)
    for i in range(cells[0]):
        for j in range(cells[1]):
            for k in range(cells[2]):
                center = ((xs[0][i]+xs[0][i+1])/2, (xs[1][j]+xs[1][j+1])/2, (xs[2][k]+xs[2][k+1])/2)
                if not shape.isInside(center, tol):
                    continue
                occupied_cells.append((i,j,k))
                ids = [get_node(i+dx, j+dy, k+dz) for dx,dy,dz in corners]
                for tet in (tetA if (i+j+k)%2 == 0 else tetB):
                    tets.append(tuple(ids[q] for q in tet))
    if len(occupied_cells) < 2 or len(nodes_mm) < 8:
        raise ValueError("Mesh is too small; increase resolution or use a larger part")
    if len(nodes_mm) > 22000:
        raise ValueError("Preview mesh too large; lower resolution")
    nodes = (np.asarray(nodes_mm, dtype=float) * scale_vec) / 1000.0
    return {
        "shape": shape, "nodes": nodes, "nodes_mm": np.asarray(nodes_mm, dtype=float) * scale_vec,
        "tets": tets, "cells": cells, "occupied_cells": occupied_cells, "grid": xs, "scale_vec": scale_vec,
    }


def _elastic_system(obj: dict[str, Any], resolution: int) -> dict[str, Any]:
    mesh = voxel_tet_mesh(obj, resolution)
    nodes = mesh["nodes"]
    n = len(nodes)
    mat = MATERIALS.get(obj.get("material"), MATERIALS["Aluminum 6061-T6"])
    E, nu = float(mat["youngs_modulus"]), float(mat["poisson"])
    lam = E*nu/((1+nu)*(1-2*nu)); mu = E/(2*(1+nu))
    D = np.array([
        [lam+2*mu,lam,lam,0,0,0],[lam,lam+2*mu,lam,0,0,0],[lam,lam,lam+2*mu,0,0,0],
        [0,0,0,mu,0,0],[0,0,0,0,mu,0],[0,0,0,0,0,mu]
    ], dtype=float)
    rows: list[int] = []; cols: list[int] = []; vals: list[float] = []
    elem_B: list[np.ndarray] = []; elem_V: list[float] = []; valid_tets: list[tuple[int,int,int,int]] = []
    node_mass = np.zeros(n, dtype=float)
    density = float(mat["density"])
    for tet in mesh["tets"]:
        xyz = nodes[list(tet)]
        M = np.column_stack([np.ones(4), xyz])
        det = np.linalg.det(M); V = abs(det)/6.0
        if V < 1e-18: continue
        invM = np.linalg.inv(M)
        B = np.zeros((6,12), dtype=float)
        for a in range(4):
            b,c,d = invM[1:,a]
            B[:,3*a:3*a+3] = [[b,0,0],[0,c,0],[0,0,d],[c,b,0],[0,d,c],[d,0,b]]
        Ke = (B.T @ D @ B) * V
        dofs = np.array([[3*q,3*q+1,3*q+2] for q in tet]).ravel()
        rows.extend(np.repeat(dofs,12).tolist()); cols.extend(np.tile(dofs,12).tolist()); vals.extend(Ke.ravel().tolist())
        for q in tet: node_mass[q] += density * V / 4.0
        elem_B.append(B); elem_V.append(V); valid_tets.append(tet)
    K = coo_matrix((vals,(rows,cols)), shape=(3*n,3*n)).tocsr()
    mesh.update({"K": K, "D": D, "elem_B": elem_B, "elem_V": elem_V, "valid_tets": valid_tets, "node_mass": node_mass, "material": mat})
    return mesh


def _boundary_nodes(nodes: np.ndarray, axis: str, side: str, cells: np.ndarray) -> np.ndarray:
    ai = AXIS[axis]; coord = nodes[:,ai]
    cmin, cmax = float(coord.min()), float(coord.max())
    cellsize = float((cmax-cmin)/max(int(cells[ai]),1))
    if side == "min": return np.where(coord <= cmin + cellsize*0.18)[0]
    return np.where(coord >= cmax - cellsize*0.18)[0]


def linear_fea(obj: dict[str, Any], force_n: float = 100.0, support_axis: str = "x", load_direction: str = "z", resolution: int = 10, samples: int = 700) -> dict[str, Any]:
    if support_axis not in AXIS or load_direction not in AXIS: raise ValueError("axes must be x, y, or z")
    sys = _elastic_system(obj, resolution)
    nodes, K, cells = sys["nodes"], sys["K"], sys["cells"]
    n = len(nodes); di = AXIS[load_direction]
    fixed_nodes = _boundary_nodes(nodes, support_axis, "min", cells)
    load_nodes = _boundary_nodes(nodes, support_axis, "max", cells)
    if len(fixed_nodes) < 3 or len(load_nodes) < 1: raise ValueError("Could not identify enough support/load nodes")
    f = np.zeros(3*n, dtype=float); f[3*load_nodes+di] = float(force_n)/len(load_nodes)
    fixed_dofs = np.unique(np.concatenate([3*fixed_nodes,3*fixed_nodes+1,3*fixed_nodes+2]))
    all_dofs = np.arange(3*n); free = np.setdiff1d(all_dofs, fixed_dofs)
    u = np.zeros(3*n, dtype=float); uf = spsolve(K[free][:,free], f[free])
    if not np.all(np.isfinite(uf)): raise ValueError("Linear system was singular")
    u[free] = uf
    vm = []
    centroids = []
    for B,tet in zip(sys["elem_B"], sys["valid_tets"]):
        edofs = np.array([[3*q,3*q+1,3*q+2] for q in tet]).ravel()
        sig = sys["D"] @ (B @ u[edofs])
        sx,sy,sz,txy,tyz,tzx = sig
        von = math.sqrt(max(0.0, 0.5*((sx-sy)**2+(sy-sz)**2+(sz-sx)**2)+3*(txy*txy+tyz*tyz+tzx*tzx)))
        vm.append(von); centroids.append(nodes[list(tet)].mean(axis=0)*1000.0)
    disp = np.linalg.norm(u.reshape(-1,3), axis=1)
    max_disp = float(disp.max()); max_vm = float(max(vm) if vm else 0.0); p95_vm = float(np.percentile(vm,95)) if vm else 0.0
    fos = float(sys["material"]["yield_strength"]) / max_vm if max_vm > 0 else float("inf")
    centroids = np.asarray(centroids); vm_arr = np.asarray(vm)/1e6
    if len(vm_arr) > samples:
        idx = np.linspace(0, len(vm_arr)-1, samples).astype(int); centroids = centroids[idx]; vm_arr = vm_arr[idx]
    return {
        "method": "voxel-tetra linear elastic FEA preview",
        "mesh": {"nodes": int(n), "tetrahedra": int(len(sys["valid_tets"])), "occupied_voxels": int(len(sys["occupied_cells"])), "cells": [int(x) for x in cells]},
        "bc": {"fixed_face": f"{support_axis}-min", "load_face": f"{support_axis}-max", "load_direction": load_direction, "total_force_n": float(force_n), "fixed_nodes": int(len(fixed_nodes)), "load_nodes": int(len(load_nodes))},
        "max_displacement_mm": max_disp*1000.0, "max_von_mises_mpa": max_vm/1e6, "p95_von_mises_mpa": p95_vm/1e6, "yield_fos": fos,
        "field": {"kind": "stress_mpa", "samples": [[float(*[])]] if False else [[float(p[0]),float(p[1]),float(p[2]),float(v)] for p,v in zip(centroids,vm_arr)]},
        "warnings": ["Preview-grade linear static analysis: small deformation, isotropic linear elasticity, and an idealized fixed support.", "Geometry is voxelized. Refine the mesh and check convergence before trusting local peak stress.", "Contact, preload, plasticity, fatigue, thermal coupling, and manufacturing variation are not included."],
    }


def modal_analysis(obj: dict[str, Any], support_axis: str = "x", resolution: int = 8, modes: int = 6) -> dict[str, Any]:
    if support_axis not in AXIS: raise ValueError("axis must be x, y, or z")
    sys = _elastic_system(obj, resolution); nodes = sys["nodes"]; n = len(nodes)
    fixed_nodes = _boundary_nodes(nodes, support_axis, "min", sys["cells"])
    fixed_dofs = np.unique(np.concatenate([3*fixed_nodes,3*fixed_nodes+1,3*fixed_nodes+2]))
    free = np.setdiff1d(np.arange(3*n), fixed_dofs)
    if len(free) < 12: raise ValueError("Not enough free DOFs for modal analysis")
    mass_diag = np.repeat(np.maximum(sys["node_mass"], 1e-12), 3)
    Kff = sys["K"][free][:,free]
    Mff = diags(mass_diag[free])
    k = max(1, min(int(modes), len(free)-2, 10))
    vals, vecs = eigsh(Kff, k=k, M=Mff, sigma=0.0, which="LM")
    vals = np.maximum(np.real(vals), 0)
    freqs = np.sqrt(vals)/(2*math.pi); order = np.argsort(freqs); freqs = freqs[order]
    return {
        "method": "lumped-mass tetrahedral modal preview", "frequencies_hz": [float(x) for x in freqs], "first_mode_hz": float(freqs[0]) if len(freqs) else None,
        "mesh": {"nodes": int(n), "tetrahedra": int(len(sys["valid_tets"])), "cells": [int(x) for x in sys["cells"]]},
        "warnings": ["Preview modal analysis uses the same voxel-tetra geometry approximation and lumped mass matrix as the structural preview solver.", "Joint compliance, fastener flexibility, damping, and contact are not represented."],
    }


def thermal_analysis(obj: dict[str, Any], heat_w: float = 10.0, ambient_c: float = 22.0, h_w_m2k: float = 8.0, resolution: int = 14, fixed_axis: str | None = None, fixed_temp_c: float | None = None, samples: int = 700) -> dict[str, Any]:
    resolution = max(4, min(int(resolution), 26))
    shape = build_shape(obj); bb = shape.BoundingBox()
    mins = np.array([bb.xmin,bb.ymin,bb.zmin],float); maxs=np.array([bb.xmax,bb.ymax,bb.zmax],float)
    dims=np.maximum(maxs-mins,1e-6); scale=np.abs(np.asarray(obj.get("transform",{}).get("scale",[1,1,1]),float)); physical=dims*scale; longest=float(physical.max())
    cells=np.maximum(2,np.round(resolution*physical/longest).astype(int)); cells=np.minimum(cells,resolution)
    steps=physical/cells/1000.0
    xs=[np.linspace(mins[i],maxs[i],cells[i]+1) for i in range(3)]
    occ: list[tuple[int,int,int]]=[]; lookup={}
    tol=max(1e-7,longest*1e-8)
    for i in range(cells[0]):
      for j in range(cells[1]):
       for k in range(cells[2]):
        center=((xs[0][i]+xs[0][i+1])/2,(xs[1][j]+xs[1][j+1])/2,(xs[2][k]+xs[2][k+1])/2)
        if shape.isInside(center,tol): lookup[(i,j,k)]=len(occ); occ.append((i,j,k))
    n=len(occ)
    if n<2: raise ValueError("Thermal mesh too small")
    mat=MATERIALS.get(obj.get("material"),MATERIALS["Aluminum 6061-T6"]); kcond=float(mat["thermal_conductivity"])
    rows=[];cols=[];vals=[];rhs=np.full(n,float(heat_w)/n)
    ambient=float(ambient_c); h=max(0,float(h_w_m2k))
    fixed_nodes=[]
    face_area=[steps[1]*steps[2],steps[0]*steps[2],steps[0]*steps[1]]
    dirs=[(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]
    for idx,(i,j,k) in enumerate(occ):
        diag=0.0
        for di,dj,dk in dirs:
            nb=(i+di,j+dj,k+dk); axis=0 if di else 1 if dj else 2
            if nb in lookup:
                g=kcond*face_area[axis]/max(steps[axis],1e-12); diag+=g; rows.append(idx);cols.append(lookup[nb]);vals.append(-g)
            else:
                g=h*face_area[axis]; diag+=g; rhs[idx]+=g*ambient
        rows.append(idx);cols.append(idx);vals.append(diag)
        if fixed_axis in AXIS and fixed_temp_c is not None:
            ai=AXIS[fixed_axis]; coord=(i,j,k)[ai]
            if coord==0: fixed_nodes.append(idx)
    A=coo_matrix((vals,(rows,cols)),shape=(n,n)).tolil()
    if fixed_nodes:
        ft=float(fixed_temp_c)
        for idx in fixed_nodes:
            A.rows[idx]=[idx];A.data[idx]=[1.0];rhs[idx]=ft
    T=spsolve(A.tocsr(),rhs)
    if not np.all(np.isfinite(T)): raise ValueError("Thermal solve failed")
    centers=[]
    for i,j,k in occ:
        centers.append([((xs[0][i]+xs[0][i+1])/2)*scale[0],((xs[1][j]+xs[1][j+1])/2)*scale[1],((xs[2][k]+xs[2][k+1])/2)*scale[2]])
    centers=np.asarray(centers)
    if n>samples:
        si=np.linspace(0,n-1,samples).astype(int); centers=centers[si]; Tout=T[si]
    else: Tout=T
    return {
        "method":"voxel finite-volume steady-state conduction preview", "max_temperature_c":float(np.max(T)), "min_temperature_c":float(np.min(T)), "avg_temperature_c":float(np.mean(T)),
        "heat_w":float(heat_w), "ambient_c":ambient, "convection_h_w_m2k":h, "mesh":{"cells":[int(x) for x in cells],"occupied_voxels":n},
        "field":{"kind":"temperature_c","samples":[[float(p[0]),float(p[1]),float(p[2]),float(v)] for p,v in zip(centers,Tout)]},
        "warnings":["Preview steady-state conduction/convection model. Radiation, contact resistance, internal airflow, phase change, and temperature-dependent properties are not included.","Voxel boundaries approximate curved geometry; refine resolution for convergence."],
    }


def optimize_part(obj: dict[str, Any], variables: list[dict[str, Any]], objective: str = "mass", force_n: float = 100.0, axis: str = "x", deflection_max_mm: float | None = None, yield_fos_min: float | None = None, max_evals: int = 90) -> dict[str, Any]:
    if not variables: raise ValueError("At least one variable is required")
    names=[];bounds=[]
    for v in variables[:6]:
        name=str(v["param"])
        if name not in obj.get("params",{}) or not isinstance(obj["params"].get(name),(int,float)): raise ValueError(f"{name} is not a numeric part parameter")
        lo=float(v["min"]);hi=float(v["max"])
        if not lo<hi: raise ValueError(f"Invalid bounds for {name}")
        names.append(name);bounds.append((lo,hi))
    baseline=deepcopy(obj); baseline_metrics=object_metrics(baseline); base_screen=quick_cantilever(baseline,force_n,axis=axis)
    seen=[]
    def score(x):
        trial=deepcopy(obj)
        for name,val in zip(names,x): trial["params"][name]=float(val)
        try:
            met=object_metrics(trial); screen=quick_cantilever(trial,force_n,axis=axis)
            value=met["mass_kg"] if objective=="mass" else met["volume_mm3"]
            penalty=0.0
            if deflection_max_mm is not None and screen["deflection_mm"]>deflection_max_mm: penalty += value*1000*(screen["deflection_mm"]/deflection_max_mm-1+1e-3)
            if yield_fos_min is not None and screen["yield_fos"]<yield_fos_min: penalty += value*1000*(yield_fos_min/max(screen["yield_fos"],1e-6)-1+1e-3)
            total=float(value+penalty);seen.append((total,[float(v) for v in x],met,screen));return total
        except Exception:
            return 1e30
    pop=max(5,min(10,max_evals//8));iters=max(1,min(12,max_evals//pop-1))
    res=differential_evolution(score,bounds,popsize=pop,maxiter=iters,tol=0.03,polish=True,seed=42,workers=1,updating="immediate")
    best=deepcopy(obj)
    for name,val in zip(names,res.x): best["params"][name]=float(val)
    best_met=object_metrics(best);best_screen=quick_cantilever(best,force_n,axis=axis)
    feasible=(deflection_max_mm is None or best_screen["deflection_mm"]<=deflection_max_mm) and (yield_fos_min is None or best_screen["yield_fos"]>=yield_fos_min)
    top=[]
    for _,x,met,scr in sorted(seen,key=lambda z:z[0])[:12]: top.append({"params":dict(zip(names,x)),"mass_kg":met["mass_kg"],"deflection_mm":scr["deflection_mm"],"yield_fos":scr["yield_fos"]})
    return {"method":"differential-evolution parameter optimization using analytical screening constraints","objective":objective,"variables":names,"baseline":{"params":{n:obj["params"][n] for n in names},"mass_kg":baseline_metrics["mass_kg"],"deflection_mm":base_screen["deflection_mm"],"yield_fos":base_screen["yield_fos"]},"best":{"params":{n:float(best["params"][n]) for n in names},"mass_kg":best_met["mass_kg"],"deflection_mm":best_screen["deflection_mm"],"yield_fos":best_screen["yield_fos"],"feasible":feasible},"candidates":top,"evaluations":len(seen),"warnings":["Optimization uses the fast cantilever screening model for structural constraints. Re-run FEA on the selected candidate before fabrication."]}


def manufacturing_review(obj: dict[str, Any], process: str = "fdm") -> dict[str, Any]:
    process=process.lower(); met=object_metrics(obj); dims=sorted(met["bbox_mm"]); features=obj.get("features",[]); findings=[]; score=100
    if process in {"fdm","sla","sls"}:
        if dims[0] < 1.0: findings.append({"severity":"high","message":f"Minimum bounding thickness is only {dims[0]:.2f} mm; verify printable wall thickness."});score-=25
        for f in features:
            if f.get("type")=="hole" and float(f.get("diameter",99))<2.0: findings.append({"severity":"medium","message":f"{f.get('name','Hole')} is under 2 mm and may print undersize."});score-=8
        findings.append({"severity":"info","message":"Overhangs and support accessibility require face-level analysis; this preview does not yet compute local overhang angle."})
    elif process=="cnc":
        for f in features:
            if f.get("type") in {"pocket_rect","pocket_circle"}:
                depth=float(f.get("depth",0)); width=float(f.get("diameter",f.get("width",1)))
                if width>0 and depth/width>4: findings.append({"severity":"medium","message":"A pocket has depth/width > 4; tool reach and chatter may be problematic."});score-=10
        if not any(f.get("type")=="fillet_all" for f in features): findings.append({"severity":"info","message":"No fillet feature is present. Internal milled corners require a tool radius even if the nominal CAD edge is sharp."})
    elif process=="laser":
        if dims[0] > 20: findings.append({"severity":"medium","message":"Part is relatively thick for common laser-cut workflows; verify material/process capability."});score-=10
        if len(obj.get("features",[]))>0: findings.append({"severity":"info","message":"Only through-cut planar features are directly compatible with 2D laser cutting."})
    else:
        findings.append({"severity":"info","message":"No dedicated heuristics for this process yet."})
    if not findings: findings.append({"severity":"pass","message":"No obvious process-screening issues found."})
    return {"process":process,"score":max(0,score),"findings":findings,"metrics":met,"warnings":["Manufacturing review is heuristic screening, not a supplier quote or process plan."]}


def system_capabilities() -> dict[str, Any]:
    def which(*names: str) -> str | None:
        for n in names:
            p=shutil.which(n)
            if p:return p
        return None
    ram_gb=None
    try:
        if hasattr(os,"sysconf"):
            pages=os.sysconf("SC_PHYS_PAGES"); page=os.sysconf("SC_PAGE_SIZE"); ram_gb=pages*page/1024**3
    except Exception: pass
    optional={
        "gmsh":which("gmsh"),"calculix":which("ccx","calculix"),"elmer":which("ElmerSolver"),"openfoam":which("foamRun","simpleFoam"),"code_aster":which("as_run"),
    }
    return {"platform":platform.platform(),"machine":platform.machine(),"python":platform.python_version(),"cpu_count":os.cpu_count(),"ram_gb":round(ram_gb,1) if ram_gb else None,"built_in":{"cadquery_opencascade":True,"linear_fea":True,"modal":True,"thermal":True,"optimization":True,"rapier_client":True},"external_solvers":{k:{"available":bool(v),"path":v} for k,v in optional.items()},"notes":["Built-in structural, modal, and thermal solvers are preview-grade design tools.","External high-fidelity solvers are detected automatically when installed; adapters can be added without changing the canonical project model."]}
