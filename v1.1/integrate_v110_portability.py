from __future__ import annotations
from pathlib import Path
import sys
root=Path(sys.argv[1] if len(sys.argv)>1 else 'v1.1/base').resolve()

def one(s,old,new,label):
    if old not in s:raise SystemExit(f'anchor missing: {label}')
    return s.replace(old,new,1)

p=root/'component_registry.py';s=p.read_text(encoding='utf-8')
old='''def component_snapshot(cid):return {k:deepcopy(v) for k,v in component_by_id(cid).items() if k!="legacy"}\n'''
new='''def component_snapshot(cid):\n    snap={k:deepcopy(v) for k,v in component_by_id(cid).items() if k!="legacy"}\n    for asset in snap.get("geometry",{}).get("assets",[]):asset.pop("path",None)\n    return snap\n\ndef resolve_asset_path(asset):\n    rel=asset.get("relative_path")\n    if rel:\n        p=(ASSET_DIR/str(rel)).resolve()\n        try:p.relative_to(ASSET_DIR.resolve())\n        except ValueError:return None\n        return p\n    old=asset.get("path")\n    if old:\n        p=Path(str(old));return p if p.is_file() else None\n    return None\n'''
s=one(s,old,new,'component snapshot portability')
old='''    folder=ASSET_DIR/_slug(cid);folder.mkdir(parents=True,exist_ok=True);out=folder/f"{digest[:16]}_{_safe_asset_name(filename)}";out.write_bytes(data);asset={"id":digest[:16],"role":role,"filename":filename,"path":str(out),"sha256":digest,"bytes":len(data),"format":ext.lstrip("."),"source":_source(source_kind,source_url)};component.setdefault("geometry",{}).setdefault("assets",[]).append(asset)\n'''
new='''    folder=ASSET_DIR/_slug(cid);folder.mkdir(parents=True,exist_ok=True);out=folder/f"{digest[:16]}_{_safe_asset_name(filename)}";out.write_bytes(data);rel=str(out.relative_to(ASSET_DIR)).replace("\\\\","/");asset={"id":digest[:16],"role":role,"filename":filename,"relative_path":rel,"sha256":digest,"bytes":len(data),"format":ext.lstrip("."),"source":_source(source_kind,source_url)};component.setdefault("geometry",{}).setdefault("assets",[]).append(asset)\n'''
s=one(s,old,new,'relative asset path')
p.write_text(s,encoding='utf-8')

p=root/'physical_components.py';s=p.read_text(encoding='utf-8')
old='''def _step_asset(c):\n    if not c:return None\n    for a in c.get("geometry",{}).get("assets",[]):\n        if a.get("role")=="geometry" and a.get("format") in {"step","stp"} and Path(str(a.get("path",""))).is_file():return Path(a["path"])\n    return None\n'''
new='''def _step_asset(c):\n    if not c:return None\n    for a in c.get("geometry",{}).get("assets",[]):\n        if a.get("role")=="geometry" and a.get("format") in {"step","stp"}:\n            path=registry.resolve_asset_path(a)\n            if path and path.is_file():return path\n    return None\n'''
s=one(s,old,new,'STEP asset resolution')
p.write_text(s,encoding='utf-8')

p=root/'server.py';s=p.read_text(encoding='utf-8')
s=one(s,'import component_importers\nimport physical_components','import component_importers\nimport physical_components\nimport project_bundle','bundle import')
anchor='''@app.get("/api/export")\ndef export():return core.PROJECT\n'''
replacement=anchor+'''@app.get("/api/project/bundle")\ndef export_bundle():\n    data=project_bundle.export_bundle_bytes(core.PROJECT);return Response(content=data,media_type="application/zip",headers={"Content-Disposition":"attachment; filename=ForgeCAD-project.forgecad.zip"})\n@app.post("/api/project/import-bundle")\nasync def import_bundle(file:UploadFile=File(...)):\n    try:\n        result=project_bundle.import_bundle_bytes(await file.read());st=core.upgrade_project(result["project"]);core.PROJECT.clear();core.PROJECT.update(st);core.push_history("import portable project bundle","human","restore canonical project plus component assets");core.persist();result["project"]=core.PROJECT;return result\n    except Exception as e:fail(e)\n'''
s=one(s,anchor,replacement,'bundle API')
p.write_text(s,encoding='utf-8')
print('integrated portable component assets and project bundles')
