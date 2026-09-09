from __future__ import annotations
import os,tempfile
_tmp=tempfile.TemporaryDirectory();os.environ['FORGECAD_DATA_DIR']=_tmp.name
from fastapi.testclient import TestClient
import server,core
c=TestClient(server.app)
assert c.get('/api/health').status_code==200
assert c.get('/api/tools').status_code==200
assert c.get('/api/components').json()['total']>=200
o=core.PROJECT['objects'][0]['id'];assert c.get('/api/mesh/'+o).status_code==200;assert c.post('/api/analyze/fea/'+o+'?force_n=250').status_code==200
assert c.post('/api/branch',json={'op':'branch','args':{'name':'api-branch'}}).status_code==200
pi=next(x for x in core.PROJECT['objects'] if x.get('code'))['id'];assert c.get('/api/code/'+pi).status_code==200
# Jarvis endpoints reject uncredentialed callers.
assert c.get('/api/jarvis/status').status_code==401
print('ForgeCAD v1 API contract: PASS')
