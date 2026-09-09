from __future__ import annotations
import os,tempfile
from pathlib import Path
_tmp=tempfile.TemporaryDirectory();os.environ['FORGECAD_DATA_DIR']=_tmp.name
import cadquery as cq
from fastapi.testclient import TestClient
import core,server

client=TestClient(server.app)
def ok(resp,label):
    if resp.status_code>=400:raise AssertionError(f"{label}: {resp.status_code} {resp.text}")
    return resp.json()

def check(cond,label):
    if not cond:raise AssertionError(label)

h=ok(client.get('/api/health'),'health');check(h['version'].startswith('1.1'),'API version')
stats=ok(client.get('/api/components/stats'),'registry stats');check(stats['total']>=200,'registry count')
schema=ok(client.get('/api/components/schema'),'registry schema');check('interfaces' in schema['required'],'schema interfaces')
search=ok(client.post('/api/components/search',json={'query':'raspberry pi','limit':5,'min_trust':50}),'search');check(search['results'][0]['trust_score']>=50,'trust filter')
selected=ok(client.post('/api/components/select',json={'category':'stepper_motor','requirements':{'min_holding_torque_nm':.5},'limit':8}),'select');check(selected['best']['recommended'],'constraint selection')

ok(client.post('/api/components/add/motor.nema17.48'),'add stepper');ok(client.post('/api/components/add/bearing.6000.5'),'add bearing');project=ok(client.get('/api/project'),'project');stepper=next(o for o in project['objects'] if o.get('component_ref')=='motor.nema17.48');bearing=next(o for o in project['objects'] if o.get('component_ref')=='bearing.6000.5');check(stepper.get('component_snapshot') and bearing.get('interfaces'),'component snapshots through API')
compatible=ok(client.get('/api/components/motor.nema17.48/compatible/bearing.6000.5'),'compatibility');check(any(x['a']['id']=='output_shaft' and x['b']['id']=='shaft_bore' for x in compatible['interfaces']),'compatible interfaces endpoint')
ok(client.post('/api/assembly/mate',json={'source_id':bearing['id'],'source_interface':'shaft_bore','target_id':stepper['id'],'target_interface':'output_shaft','gap_mm':0}),'mate');project=ok(client.get('/api/project'),'project after mate');check(project['connections'],'mating connection persisted')
reality=ok(client.get('/api/reality-check'),'reality');check('counts' in reality and reality['components']>=3,'reality endpoint')

custom={'id':'custom.api.sensor','category':'sensor','manufacturer':'API Co','model':'Sense-1','name':'API Co Sense-1','dimensions_mm':[20,14,4],'mass_g':5,'voltage_v':3.3,'sensor_type':'distance'}
imported=ok(client.post('/api/components/import',json=custom),'JSON component import');check(imported['added'][0]['id']=='custom.api.sensor','JSON import ID')

# Vendor STEP becomes a reusable registry component rather than anonymous geometry.
step=Path(_tmp.name)/'api_vendor.step';cq.exporters.export(cq.Workplane('XY').box(16,11,7).val(),str(step),exportType='STEP')
with step.open('rb') as f:
    resp=client.post('/api/components/import-step-component?manufacturer=VendorCo&model=Block16&category=custom&source_kind=manufacturer&source_url=https%3A%2F%2Fexample.com%2Fblock16',files={'file':('block16.step',f,'model/step')})
vendor=ok(resp,'vendor STEP import');check(vendor['component']['geometry']['fidelity']=='official_step','vendor STEP fidelity');cid=vendor['component']['id'];ok(client.post('/api/components/add/'+cid),'add imported STEP component');project=ok(client.get('/api/project'),'project imported component');vo=next(o for o in project['objects'] if o.get('component_ref')==cid);metrics=ok(client.get('/api/metrics'),'metrics');bounds=metrics['objects'][vo['id']]['bounds_mm'];check(abs(bounds['x']-16)<.05 and abs(bounds['z']-7)<.05,'STEP geometry used by API mesh model')

openapi=ok(client.get('/openapi.json'),'openapi');paths=openapi['paths'];required=['/api/components/select','/api/components/import-step-component','/api/assembly/mate','/api/reality-check']
check(all(x in paths for x in required),'v1.1 routes published in OpenAPI')
tools=ok(client.get('/api/tools'),'tools');check('add_component' in tools['operations'] and 'mate_components' in tools['operations'],'agent tool contract')
print('ForgeCAD v1.1 API test: PASS',{'paths':len(paths),'components':stats['total'],'connections':len(project['connections'])})
