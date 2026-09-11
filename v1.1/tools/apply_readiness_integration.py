from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected exactly one target, found {count}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')


replace_once(
    'v1.1/base/server.py',
    'import physical_components\nimport project_bundle\n',
    'import physical_components\nimport production_readiness\nimport project_bundle\n',
)
replace_once(
    'v1.1/base/server.py',
    '''@app.post("/api/design/status")
def design_status(body:DesignStatusBody):
    try:return core.set_design_status(body.name,body.status,body.note,body.physical_verified)
    except KeyError as e:fail(e,404)
''',
    '''@app.post("/api/design/status")
def design_status(body:DesignStatusBody):
    try:
        if body.physical_verified:
            state=core.PROJECT if body.name==core.ACTIVE_DESIGN else core.BRANCHES.get(body.name)
            if state is None:raise KeyError(body.name)
            readiness=production_readiness.assess(state,core.build_shape)
            if not readiness["ready_for_physical_verification"]:
                codes=", ".join(str(x.get("code")) for x in readiness["blockers"][:6])
                raise HTTPException(409,f"This design cannot be marked physically verified yet. Resolve: {codes or 'production-readiness blockers'}")
        return core.set_design_status(body.name,body.status,body.note,body.physical_verified)
    except HTTPException:raise
    except KeyError as e:fail(e,404)
''',
)
replace_once(
    'v1.1/base/server.py',
    '''@app.get("/api/reality-check")
def reality_check():return core.reality_check()
@app.get("/api/system-check")
def system_check():return core.reality_check()
''',
    '''@app.get("/api/reality-check")
def reality_check():return core.reality_check()
@app.get("/api/production-readiness")
def production_ready():return production_readiness.assess(core.PROJECT,core.build_shape)
@app.get("/api/system-check")
def system_check():return core.reality_check()
''',
)

# Add explicit design-status and production-readiness controls to the current UI.
replace_once(
    'v1.1/base/static/index.html',
    '<button id="newBranchBtn" class="plus">＋ Branch</button><button id="compareBtn">Compare</button>',
    '<button id="newBranchBtn" class="plus">＋ Branch</button><button id="compareBtn">Compare</button><button id="statusBtn">Design status…</button><button id="readinessBtn">Production readiness</button>',
)

p = Path('v1.1/base/static/app.js')
s = p.read_text(encoding='utf-8')
anchor = '''async function compareDesign(){const others=S.designs.designs.filter(x=>!x.active);if(!others.length)return alert('Create another design first.');const target=prompt('Compare current design against:',others[0].name);if(!target)return;const d=await api('/api/branch/compare/'+encodeURIComponent(target));showModal(`Diff: ${d.source} → ${d.target}`,d.changes.length?d.changes.map(x=>`<div class="diffItem"><b>${esc(x.type)}</b> — ${esc(x.name||x.id)}</div>`).join(''):'<p class="okText">No canonical object differences.</p>')}
'''
addition = anchor + '''async function showProductionReadiness(){try{const r=await api('/api/production-readiness');const blockers=r.blockers||[],warnings=r.warnings||[];showModal('Production readiness',`<div class="diffItem"><b>${r.ready_for_physical_verification?'ELIGIBLE FOR PHYSICAL VERIFICATION':'NOT READY'}</b> — ${blockers.length} blockers • ${warnings.length} warnings</div>${blockers.map(x=>`<div class="diffItem errorText"><b>${esc(x.code)}</b> — ${esc(x.message)}</div>`).join('')}${warnings.slice(0,20).map(x=>`<div class="diffItem"><b>${esc(x.code||x.severity)}</b> — ${esc(x.message)}</div>`).join('')}<p><small>${esc(r.disclaimer||'')}</small></p>`)}catch(e){alert(e.message)}}
async function setDesignStatus(){const active=S.designs?.active||'main',meta=S.designs?.designs?.find(x=>x.active)||{};showModal('Design status',`<div class="field"><label>Status</label><select id="statusValue"><option value="untested" ${meta.status==='untested'?'selected':''}>Untested</option><option value="working" ${meta.status==='working'?'selected':''}>Working</option><option value="not_working" ${meta.status==='not_working'?'selected':''}>Not working</option></select></div><div class="field"><label>Note</label><input id="statusNote" value="${esc(meta.note||'')}"></div><label class="checkboxRow"><input id="physicalVerified" type="checkbox" ${meta.physical_verified?'checked':''}> I physically tested this exact design</label><p><small>Physical verification is allowed only after the model passes the production-readiness gate. Passing that gate is not itself proof that the design works or is safe.</small></p><button id="statusCheck">Check readiness</button> <button id="statusSave" class="primary">Save status</button>`);$('#statusCheck').onclick=showProductionReadiness;$('#statusSave').onclick=async()=>{try{await api('/api/design/status',{method:'POST',body:JSON.stringify({name:active,status:$('#statusValue').value,note:$('#statusNote').value,physical_verified:$('#physicalVerified').checked})});$('#modal').classList.add('hidden');await refresh()}catch(e){alert(e.message)}}}
'''
if s.count(anchor) != 1:
    raise SystemExit(f'app.js compareDesign anchor count={s.count(anchor)}')
s = s.replace(anchor, addition, 1)
boot_old = "$('#newBranchBtn').onclick=createBranch;$('#compareBtn').onclick=compareDesign;$('#addPrimitiveBtn').onclick=addPrimitive;"
boot_new = "$('#newBranchBtn').onclick=createBranch;$('#compareBtn').onclick=compareDesign;$('#statusBtn').onclick=setDesignStatus;$('#readinessBtn').onclick=showProductionReadiness;$('#addPrimitiveBtn').onclick=addPrimitive;"
if s.count(boot_old) != 1:
    raise SystemExit(f'app.js bootstrap anchor count={s.count(boot_old)}')
s = s.replace(boot_old, boot_new, 1)
p.write_text(s, encoding='utf-8')

print('Production-readiness API/UI integration applied')
