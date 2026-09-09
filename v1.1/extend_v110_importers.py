from __future__ import annotations
from pathlib import Path
import sys
root=Path(sys.argv[1] if len(sys.argv)>1 else 'v1.1/base').resolve()

def one(s,old,new,label):
    if old not in s:raise SystemExit(f'anchor missing: {label}')
    return s.replace(old,new,1)

p=root/'server.py';s=p.read_text(encoding='utf-8')
s=one(s,'import component_registry as components\nimport physical_components','import component_registry as components\nimport component_importers\nimport physical_components','importer import')
anchor='''@app.post("/api/components/import-pack")\nasync def comp_import_pack(file:UploadFile=File(...)):\n    try:return components.import_catalog_pack_bytes(file.filename or "catalog.json",await file.read())\n    except Exception as e:fail(e)\n'''
replacement=anchor+'''@app.post("/api/components/import-step-component")\nasync def comp_import_step_component(file:UploadFile=File(...),manufacturer:str="Custom",model:str="Vendor Component",category:str="custom",component_id:str|None=None,manufacturer_part_number:str|None=None,mass_g:float|None=None,source_kind:str="user_supplied",source_url:str|None=None):\n    try:return component_importers.import_step_component(file.filename or "component.step",await file.read(),manufacturer=manufacturer,model=model,category=category,component_id=component_id,manufacturer_part_number=manufacturer_part_number,mass_g=mass_g,source_kind=source_kind,source_url=source_url)\n    except Exception as e:fail(e)\n'''
s=one(s,anchor,replacement,'STEP component endpoint');p.write_text(s,encoding='utf-8')

p=root/'static/app.js';s=p.read_text(encoding='utf-8')
old='<button id="realityBtn">Reality check</button><button id="importPackBtn">Import catalog pack…</button><input id="catalogPackFile" type="file" accept=".json,.zip" hidden>'
new='<button id="realityBtn">Reality check</button><button id="importStepBtn">Import vendor STEP…</button><button id="importPackBtn">Import catalog pack…</button><input id="vendorStepFile" type="file" accept=".step,.stp" hidden><input id="catalogPackFile" type="file" accept=".json,.zip" hidden>'
s=one(s,old,new,'STEP UI button')
old="$('#realityBtn').onclick=runRealityCheck;$('#importPackBtn').onclick=()=>$('#catalogPackFile').click();"
new="$('#realityBtn').onclick=runRealityCheck;$('#importStepBtn').onclick=()=>$('#vendorStepFile').click();$('#vendorStepFile').onchange=async e=>{const f=e.target.files?.[0];if(!f)return;const manufacturer=prompt('Manufacturer','Custom')||'Custom';const model=prompt('Model / part number',f.name.replace(/\\.(step|stp)$/i,''))||'Vendor Component';const category=prompt('Category (e.g. sensor, stepper_motor, solenoid, custom)','custom')||'custom';const source=prompt('Source URL (optional)','')||'';const official=confirm('Is this STEP file supplied by the manufacturer?');const fd=new FormData();fd.append('file',f);const qs=new URLSearchParams({manufacturer,model,category,source_kind:official?'manufacturer':'user_supplied'});if(source)qs.set('source_url',source);try{const r=await apiForm('/api/components/import-step-component?'+qs,fd);alert(`Imported ${r.component.name} as ${r.component.id}.\\nGeometry: ${r.component.geometry.fidelity}.`);renderComponents()}catch(err){alert(err.message)}};$('#importPackBtn').onclick=()=>$('#catalogPackFile').click();"
s=one(s,old,new,'STEP UI handler');p.write_text(s,encoding='utf-8')
print('extended vendor STEP importer API/UI')
