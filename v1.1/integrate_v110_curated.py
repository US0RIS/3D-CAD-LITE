from __future__ import annotations
from pathlib import Path
import sys
root=Path(sys.argv[1] if len(sys.argv)>1 else 'v1.1/base').resolve()

def one(s,old,new,label):
    if old not in s:raise SystemExit(f'anchor missing: {label}')
    return s.replace(old,new,1)

p=root/'component_registry.py';s=p.read_text(encoding='utf-8')
s=one(s,'import components as legacy_components','import components as legacy_components\nimport curated_catalog','curated import')
old='''def _load_builtin():\n    _BUILTIN.clear()\n    for legacy in legacy_components.REGISTRY:\n        item=_deep_merge(_normalize_legacy(legacy),ENRICHMENTS.get(legacy["id"],{}));validate_component(item);_BUILTIN[item["id"]]=item\n'''
new='''def _load_builtin():\n    _BUILTIN.clear()\n    for legacy in legacy_components.REGISTRY:\n        item=_deep_merge(_normalize_legacy(legacy),ENRICHMENTS.get(legacy["id"],{}));validate_component(item);_BUILTIN[item["id"]]=item\n    # Specific manufacturer-sourced parts override generic envelope choices only by ID, never silently.\n    for raw in curated_catalog.CATALOG:\n        item=_normalize_custom(raw,"manufacturer");validate_component(item);_BUILTIN[item["id"]]=item\n'''
s=one(s,old,new,'load curated')
old='''def import_components(payload,*,replace=True,source_kind="user_supplied"):\n    items=payload.get("components",[]) if isinstance(payload,dict) and "components" in payload else (payload if isinstance(payload,list) else [payload]);added=[]\n    for raw in items:\n        item=_normalize_custom(raw,source_kind)\n        if item["id"] in _BUILTIN and not replace:raise ValueError(f"Cannot replace built-in component {item['id']}")\n        _CUSTOM[item["id"]]=item;added.append(deepcopy(item))\n    _persist_custom();return {"ok":True,"added":added,"total_registry":len(_all_map())}\n'''
new='''def _refresh_compat_registry():\n    global REGISTRY\n    if "REGISTRY" in globals():REGISTRY[:]=list(_all_map().values())\n\ndef import_components(payload,*,replace=True,source_kind="user_supplied"):\n    items=payload.get("components",[]) if isinstance(payload,dict) and "components" in payload else (payload if isinstance(payload,list) else [payload]);added=[]\n    for raw in items:\n        item=_normalize_custom(raw,source_kind)\n        if item["id"] in _BUILTIN and not replace:raise ValueError(f"Cannot replace built-in component {item['id']}")\n        _CUSTOM[item["id"]]=item;added.append(deepcopy(item))\n    _persist_custom();_refresh_compat_registry();return {"ok":True,"added":added,"total_registry":len(_all_map())}\n'''
s=one(s,old,new,'refresh import compatibility list')
s=one(s,'_CUSTOM[cid]=component;_persist_custom();return {"ok":True,"component":component,"asset":asset}','_CUSTOM[cid]=component;_persist_custom();_refresh_compat_registry();return {"ok":True,"component":component,"asset":asset}','asset refresh')
s=one(s,'del _CUSTOM[cid];_persist_custom();return {"ok":True,"id":cid,"total_registry":len(_all_map())}','del _CUSTOM[cid];_persist_custom();_refresh_compat_registry();return {"ok":True,"id":cid,"total_registry":len(_all_map())}','delete refresh')
p.write_text(s,encoding='utf-8')

p=root/'physical_components.py';s=p.read_text(encoding='utf-8')
anchor='''def _battery_parts(c):\n    x,y,z=[float(v) for v in c["dimensions_mm"]];body,_=_box(x,y,z,"#45484d",radius=min(4,min(x,y,z)*.12));lead1=_cyl(1.2,min(15,x*.2),"#d43c35",(x/2+min(15,x*.2)/2,2,0),"x")[0];lead2=_cyl(1.2,min(15,x*.2),"#25282b",(x/2+min(15,x*.2)/2,-2,0),"x")[0];return [(body,"#45484d"),(lead1,"#d43c35"),(lead2,"#25282b")]\n'''
addition=anchor+'''def _power_supply_parts(c):\n    x,y,z=[float(v) for v in c["dimensions_mm"]];base,_=_box(x,y,1.2,"#aab0b4",(0,0,-z/2+.6),1);side1,_=_box(x,1.2,z,"#9ba1a6",(0,-y/2+.6,0),.5);side2,_=_box(x,1.2,z,"#9ba1a6",(0,y/2-.6,0),.5);end,_=_box(1.2,y,z,"#9ba1a6",(-x/2+.6,0,0),.5);top,_=_box(x*.72,y*.86,1.0,"#b4b9bd",(x*.08,0,z/2-.5),1);terminal,_=_box(12,min(55,y*.55),12,"#303337",(x/2-8,-y*.15,z/2-6),1);vents=[]\n    for i in range(8):vents.append(_box(x*.34,2,.7,"#596066",(-x*.12,-y*.31+i*y*.075,z/2+.15),.2)[0])\n    return [(base,"#aab0b4"),(side1,"#9ba1a6"),(side2,"#9ba1a6"),(end,"#9ba1a6"),(top,"#b4b9bd"),(terminal,"#303337"),(cq.Compound.makeCompound(vents),"#596066")]\n'''
s=one(s,anchor,addition,'power supply geometry')
s=one(s,'"battery":_battery_parts};fn=dispatch.get(profile)','"battery":_battery_parts,"power_supply":_power_supply_parts};fn=dispatch.get(profile)','power supply dispatch')
p.write_text(s,encoding='utf-8')
print('integrated manufacturer-curated v1.1 catalog')
