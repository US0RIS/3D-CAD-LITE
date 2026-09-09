from __future__ import annotations
from pathlib import Path
import sys

root=Path(sys.argv[1] if len(sys.argv)>1 else "v1.1/base")
path=root/"static"/"app.js"
text=path.read_text(encoding="utf-8")

old='''<div><button id="realityBtn">Reality check</button><button id="importStepBtn">Import vendor STEP…</button><button id="importPackBtn">Import catalog pack…</button>'''
new='''<div><button id="acceptanceBtn">Load v1.1 acceptance</button><button id="realityBtn">Reality check</button><button id="importStepBtn">Import vendor STEP…</button><button id="importPackBtn">Import catalog pack…</button>'''
if new not in text:
    if old not in text:raise RuntimeError("component registry header anchor not found")
    text=text.replace(old,new,1)

old_bind='''$('#realityBtn').onclick=runRealityCheck;$('#importStepBtn').onclick=()=>$('#vendorStepFile').click();'''
new_bind='''$('#acceptanceBtn').onclick=async()=>{if(!confirm('Replace the current workspace with the deterministic v1.1 acceptance assembly? The current workspace remains recoverable only if it was previously saved/exported.'))return;try{const r=await api('/api/templates/v1.1-acceptance',{method:'POST'});S.selected=null;await refresh({geometry:true,fitView:true});const sys=r.report?.system||{},assy=r.report?.assembly||{};showModal('v1.1 acceptance assembly',`<p class="okText">Loaded the canonical real-system acceptance assembly.</p><div class="diffItem"><b>System graph</b> — ${sys.ok?'PASS':'FAIL'} • ${sys.counts?.error??0} errors • ${sys.counts?.warning??0} warnings</div><div class="diffItem"><b>Physical assembly</b> — ${assy.ok?'PASS':'FAIL'} • ${assy.counts?.error??0} collisions/errors • ${assy.counts?.warning??0} warnings</div><div class="diffItem"><b>Objects</b> — ${r.project?.objects?.length??0} canonical objects • ${r.project?.connections?.length??0} semantic connections</div>`)}catch(err){alert(err.message)}};$('#realityBtn').onclick=runRealityCheck;$('#importStepBtn').onclick=()=>$('#vendorStepFile').click();'''
if new_bind not in text:
    if old_bind not in text:raise RuntimeError("component registry binding anchor not found")
    text=text.replace(old_bind,new_bind,1)

old_reality='''async function runRealityCheck(){const r=await api('/api/reality-check');showModal(`Reality check • ${r.counts.error} errors • ${r.counts.warning} warnings`,r.risks.length?r.risks.map(x=>`<div class="diffItem"><b>${esc(x.severity.toUpperCase())}</b> — ${esc(x.message)}</div>`).join(''):'<p class="okText">No component-system issues detected by the current checks.</p>')}'''
new_reality='''async function runRealityCheck(){const r=await api('/api/reality-check');const assy=r.assembly||{};const summary=`<div class="diffItem"><b>System + assembly</b> — ${r.ok?'PASS':'FAIL'} • ${r.counts.error} errors • ${r.counts.warning} warnings</div>${assy.counts?`<div class="diffItem"><b>Geometry</b> — ${assy.counts.error} errors • ${assy.counts.warning} warnings • ${assy.objects_checked??0} objects checked</div>`:''}`;showModal(`Reality check • ${r.counts.error} errors • ${r.counts.warning} warnings`,summary+(r.risks.length?r.risks.map(x=>`<div class="diffItem"><b>${esc(x.severity.toUpperCase())}</b> — ${esc(x.message)}</div>`).join(''):'<p class="okText">No component-system or physical-assembly issues detected by the current checks.</p>'))}'''
if new_reality not in text:
    if old_reality not in text:raise RuntimeError("reality check function anchor not found")
    text=text.replace(old_reality,new_reality,1)

path.write_text(text,encoding="utf-8")
print("ForgeCAD v1.1 acceptance UI integrated")
