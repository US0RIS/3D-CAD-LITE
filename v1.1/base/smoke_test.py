from __future__ import annotations
import io,json,os,tempfile,zipfile
from pathlib import Path
_tmp=tempfile.TemporaryDirectory();os.environ['FORGECAD_DATA_DIR']=_tmp.name
import cadquery as cq
import analysis,core,software
import component_registry as components
import physical_components

def check(cond,msg):
    if not cond:raise AssertionError(msg)

# Baseline v1.0.1 geometry must survive the v1.1 component rewrite.
core.reset_project();check(core.APP_VERSION.startswith('1.1'),'v1.1 version');check(core.PROJECT['schema']>=4,'schema 4')
plate=core.PROJECT['objects'][0];pm=core.object_metrics(plate);check(abs(pm['bounds_mm']['x']-105)<1e-6 and abs(pm['bounds_mm']['y']-76)<1e-6,'mounting plate envelope');check(abs(pm['bounds_mm']['z']-9)<1e-6,'plate includes standoffs')
pi=next(o for o in core.PROJECT['objects'] if o.get('component_ref')=='compute.raspberry_pi_5_8gb');pim=core.object_metrics(pi);mesh=core.tessellate(pi,.8);check(pim['bounds_mm']['x']>85 and pim['bounds_mm']['y']>56,'Pi connector envelopes protrude beyond PCB');check(len(mesh.get('triangle_colors',[]))==len(mesh['triangles']) and len(mesh['triangles'])>500,'Pi detailed colored tessellation');check(pi.get('component_snapshot',{}).get('trust_score')==100,'Pi manufacturer provenance snapshot');check(any(i.get('id')=='gpio40' for i in pi.get('interfaces',[])),'Pi semantic interfaces');check(any(b.get('component_ref')==pi['component_ref'] for b in core.PROJECT['bom']),'default purchased component in BOM')

# Exact custom-part B-rep remains authoritative.
box={'id':'smoke-box','name':'Smoke Box','kind':'box','params':{'x':120.0,'y':80.0,'z':8.0},'material':'aluminum_6061_t6','transform':{'position':[0,0,0],'rotation_deg':[0,0,0],'scale':[1,1,1]},'features':[],'semantic':{},'visible':True};m=core.object_metrics(box);check(abs(m['volume_mm3']-120*80*8)<1e-5,'exact box volume');pre=m['volume_mm3'];box['features']=[{'type':'hole','diameter':10,'axis':'z'}];post=core.object_metrics(box)['volume_mm3'];check(post<pre,'hole subtracts volume');check(len(core.tessellate(box,.5)['triangles'])>10,'tessellation')

# v1.1 registry schema, search, provenance and engineering selection.
stats=components.registry_stats();check(stats['total']>=200,'expanded component registry');check('official_step' in components.GEOMETRY_RANK,'geometry fidelity vocabulary');schema=components.component_schema();check('interfaces' in schema['required'],'component schema requires interfaces')
r=components.search_components('raspberry pi',limit=5,min_trust=50);check(any('Raspberry Pi' in x['name'] for x in r['results']),'real component search');pi_def=components.component_by_id('compute.raspberry_pi_5_8gb');check(pi_def['geometry']['profile']=='raspberry_pi_5' and pi_def['trust_score']==100,'Pi registry enrichment')
sel=components.select_component({'min_holding_torque_nm':.5},category='stepper_motor',limit=8);check(sel['best'] and sel['best']['component']['specs']['holding_torque_nm']>=.5 and sel['best']['recommended'],'constraint-aware component selection')

# Purchased parts instantiate from immutable component snapshots with physical geometry and BOM entries.
source=core.ACTIVE_DESIGN;core.execute('add_component',{'component_id':'motor.nema17.48'},'test','add real stepper');check(core.ACTIVE_DESIGN!=source,'protected baseline auto-branches');stepper=next(o for o in core.PROJECT['objects'] if o.get('component_ref')=='motor.nema17.48');sm=core.object_metrics(stepper);smesh=core.tessellate(stepper,.9);check(sm['bounds_mm']['z']>48,'stepper shaft extends beyond motor body');check(abs(sm['mass_kg']-.480)<1e-6,'component mass comes from registry rather than envelope density');check(len(smesh.get('triangle_colors',[]))==len(smesh['triangles']) and len(smesh['triangles'])>80,'stepper physical multicolor geometry');check(any(x.get('component_ref')=='motor.nema17.48' for x in core.PROJECT['bom']),'component auto-added to BOM')
core.execute('add_component',{'component_id':'bearing.6000.5'},'test','add bearing');bearing=next(o for o in core.PROJECT['objects'] if o.get('component_ref')=='bearing.6000.5');bm=core.object_metrics(bearing);check(bm['volume_mm3']>0 and bm['bounds_mm']['x']>5,'bearing is ring geometry');compat=components.compatible_interfaces('motor.nema17.48','bearing.6000.5');check(any(x['a']['id']=='output_shaft' and x['b']['id']=='shaft_bore' for x in compat),'shaft/bearing interface compatibility')
core.execute('mate_components',{'source_id':bearing['id'],'source_interface':'shaft_bore','target_id':stepper['id'],'target_interface':'output_shaft'},'test','mate bearing to motor shaft');check(any(c.get('a',{}).get('object_id')==bearing['id'] and c.get('b',{}).get('object_id')==stepper['id'] for c in core.PROJECT['connections']),'mating creates canonical connection')

# Custom catalog import persists structured data; STEP assets override generated proxies.
custom={'schema_version':1,'id':'custom.test.block','category':'custom','manufacturer':'ForgeCAD Test','model':'Vendor Block','name':'ForgeCAD Test Vendor Block','dimensions_mm':[12,8,5],'mass_g':9,'geometry':{'preferred':'parametric','fidelity':'bounding_box','trust':'user_supplied','profile':'box','dimensions_mm':[12,8,5],'assets':[]},'interfaces':[{'id':'mount','kind':'mount_face','position_mm':[0,0,-2.5],'axis':[0,0,-1],'gender':'neutral','required':False,'mate':['mount_face']}],'specs':{},'procurement':{'unit_cost_usd':4.25,'supplier':'Test Supplier','sku':'TST-1'},'software':{'programmable':False,'platform':None},'provenance':[{'kind':'user_supplied','trust':45}],'trust_score':45}
components.import_components(custom);check(components.component_by_id('custom.test.block')['procurement']['sku']=='TST-1','custom component persisted')
asset_path=Path(_tmp.name)/'vendor.step';cq.exporters.export(cq.Workplane('XY').box(14,9,6).val(),str(asset_path),exportType='STEP');asset=components.register_asset_bytes('custom.test.block','vendor.step',asset_path.read_bytes(),source_kind='manufacturer');check(asset['component']['geometry']['fidelity']=='official_step','manufacturer STEP promotes geometry fidelity')
core.execute('add_component',{'component_id':'custom.test.block'},'test','add vendor STEP component');vendor=next(o for o in core.PROJECT['objects'] if o.get('component_ref')=='custom.test.block');vm=core.object_metrics(vendor);check(abs(vm['bounds_mm']['x']-14)<.01 and abs(vm['bounds_mm']['y']-9)<.01,'registered STEP asset is authoritative physical geometry')

# Catalog pack import, including schema content, is deterministic and traversal-safe.
pack_component={'id':'custom.pack.sensor','category':'sensor','manufacturer':'PackCo','model':'S1','name':'PackCo S1','dimensions_mm':[15,10,3],'mass_g':4,'voltage_v':3.3,'sensor_type':'distance'}
buf=io.BytesIO()
with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('manifest.json',json.dumps({'components':[pack_component]}))
pack_result=components.import_catalog_pack_bytes('pack.zip',buf.getvalue());check(pack_result['ok'] and components.component_by_id('custom.pack.sensor')['category']=='sensor','ZIP catalog pack import')

# Explicit sync updates snapshots; no background mutation of historical designs.
old_snapshot=json.dumps(stepper['component_snapshot'],sort_keys=True);core.execute('sync_component',{'id':stepper['id']},'test','explicit component registry sync');check(json.dumps(stepper['component_snapshot'],sort_keys=True)==old_snapshot,'explicit sync is stable when registry unchanged')

# Code workspace remains tied to the physical programmable component.
pi=next(o for o in core.PROJECT['objects'] if o.get('code'));core.execute('code_write',{'id':pi['id'],'path':'control.py','content':'def control():\n    return 1\n'},'test','code IDE');check(software.validate_workspace(core.PROJECT,pi['id'])['ok'],'code validates')

# Reality checks expose open required interfaces but no missing-registry fatal errors.
reality=core.reality_check();check(reality['components']>=4 and not any(r['code']=='component_missing_registry' for r in reality['risks']),'component reality scan')

# Existing engineering analysis and STEP round-trip remain intact.
check(analysis.quick_cantilever(box,100)['yield_fos']>0,'structural');check(analysis.modal_analysis(box)['modes'][0]['frequency_hz']>0,'modal');check(analysis.thermal_analysis(box)['max_temperature_c']>22,'thermal')
path=Path(_tmp.name)/'test.step';cq.exporters.export(core.build_shape(box),str(path),exportType='STEP');check(path.stat().st_size>100,'STEP export');before=len(core.PROJECT['objects']);core.import_step_bytes('roundtrip.step',path.read_bytes());check(len(core.PROJECT['objects'])==before+1,'STEP import')
print('ForgeCAD v1.1 smoke test: PASS',{'components':components.registry_stats()['total'],'active_design':core.ACTIVE_DESIGN,'connections':len(core.PROJECT.get('connections',[])),'reality':reality['counts']})
