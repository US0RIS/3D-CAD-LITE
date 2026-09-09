from __future__ import annotations
import os,tempfile
from pathlib import Path
_tmp=tempfile.TemporaryDirectory();os.environ['FORGECAD_DATA_DIR']=_tmp.name
import cadquery as cq
import analysis,components,core,software

def check(cond,msg):
    if not cond:raise AssertionError(msg)
core.reset_project();plate=core.PROJECT['objects'][0];pm=core.object_metrics(plate);check(abs(pm['bounds_mm']['x']-105)<1e-6 and abs(pm['bounds_mm']['y']-76)<1e-6,'mounting plate envelope');check(abs(pm['bounds_mm']['z']-9)<1e-6,'plate includes standoffs')
pi=next(o for o in core.PROJECT['objects'] if o.get('component_ref')=='compute.raspberry_pi_5_8gb');pim=core.object_metrics(pi);mesh=core.tessellate(pi,.8);check(pim['bounds_mm']['x']>85 and pim['bounds_mm']['y']>56,'Pi connector envelopes protrude beyond PCB');check(len(mesh.get('triangle_colors',[]))==len(mesh['triangles']) and len(mesh['triangles'])>500,'Pi detailed colored tessellation')
box={'id':'smoke-box','name':'Smoke Box','kind':'box','params':{'x':120.0,'y':80.0,'z':8.0},'material':'aluminum_6061_t6','transform':{'position':[0,0,0],'rotation_deg':[0,0,0],'scale':[1,1,1]},'features':[],'semantic':{},'visible':True};m=core.object_metrics(box);check(abs(m['volume_mm3']-120*80*8)<1e-5,'exact box volume');pre=m['volume_mm3'];box['features']=[{'type':'hole','diameter':10,'axis':'z'}];post=core.object_metrics(box)['volume_mm3'];check(post<pre,'hole subtracts volume');check(len(core.tessellate(box,.5)['triangles'])>10,'tessellation')
check(len(components.REGISTRY)>=200,'expanded component registry');r=components.search_components('raspberry pi',limit=5);check(any('Raspberry Pi' in x['name'] for x in r['results']),'real component search');check(components.component_by_id('compute.raspberry_pi_5_8gb').get('geometry_profile')=='raspberry_pi_5','Pi geometry profile registered')
core.set_design_status(core.ACTIVE_DESIGN,'working_in_real_life','bench verified',True);source=core.ACTIVE_DESIGN;core.execute('add',{'kind':'box','name':'Experiment','params':{'x':10,'y':10,'z':10}},'test','protected mutation');check(core.ACTIVE_DESIGN!=source,'protected baseline auto-branches')
pi=next(o for o in core.PROJECT['objects'] if o.get('code'));core.execute('code_write',{'id':pi['id'],'path':'control.py','content':'def control():\n    return 1\n'},'test','code IDE');check(software.validate_workspace(core.PROJECT,pi['id'])['ok'],'code validates')
check(analysis.quick_cantilever(box,100)['yield_fos']>0,'structural');check(analysis.modal_analysis(box)['modes'][0]['frequency_hz']>0,'modal');check(analysis.thermal_analysis(box)['max_temperature_c']>22,'thermal')
path=Path(_tmp.name)/'test.step';cq.exporters.export(core.build_shape(box),str(path),exportType='STEP');check(path.stat().st_size>100,'STEP export');before=len(core.PROJECT['objects']);core.import_step_bytes('roundtrip.step',path.read_bytes());check(len(core.PROJECT['objects'])==before+1,'STEP import')
print('ForgeCAD smoke test: PASS',{'components':len(components.REGISTRY),'active_design':core.ACTIVE_DESIGN})
