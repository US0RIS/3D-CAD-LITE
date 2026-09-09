"""Reference Jarvis-for-MRB ForgeCAD local tool adapter.

This file intentionally uses only Python's standard library so it can live inside the
Jarvis host without importing ForgeCAD's CAD dependencies.
"""
from __future__ import annotations
import json, os, urllib.request
from pathlib import Path

def _discovery():
    p=Path(os.environ.get('LOCALAPPDATA') or (Path.home()/'AppData'/'Local'))/'ForgeCAD'/'jarvis_bridge.json'
    d=json.loads(p.read_text(encoding='utf-8'));base=str(d['base_url']).rstrip('/')
    if not base.startswith(('http://127.0.0.1:','http://localhost:')):raise RuntimeError('ForgeCAD discovery is not loopback')
    return base,str(d['token'])
def call(path,method='GET',payload=None):
    base,token=_discovery();data=None if payload is None else json.dumps(payload).encode();req=urllib.request.Request(base+path,data=data,method=method,headers={'Content-Type':'application/json','X-ForgeCAD-Jarvis-Key':token})
    with urllib.request.urlopen(req,timeout=180) as r:return json.loads(r.read().decode())
def status():return call('/api/jarvis/status')
def summary():return call('/api/jarvis/summary')
def designs():return call('/api/jarvis/designs')
def history():return call('/api/jarvis/history')
def diff(target,source=None):return call('/api/jarvis/diff?target='+target+('' if not source else '&source='+source))
def component_select(query='',category=None,constraints=None):return call('/api/jarvis/component-select','POST',{'query':query,'category':category,'constraints':constraints or {}})
def analyze(kind,object_id=None,params=None):return call('/api/jarvis/analyze','POST',{'kind':kind,'object_id':object_id,'params':params or {}})
def change(text,execute=True):return call('/api/jarvis/change','POST',{'text':text,'execute':execute,'always_branch':True})
