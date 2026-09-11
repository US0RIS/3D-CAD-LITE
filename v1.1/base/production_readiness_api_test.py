from __future__ import annotations

from fastapi.testclient import TestClient

import acceptance_design
import component_registry
import core
import server

client = TestClient(server.app)
acceptance_design.install_into_core()

r = client.get('/api/production-readiness')
assert r.status_code == 200, r.text
report = r.json()
assert report['ready_for_physical_verification'] is True, report

active = core.ACTIVE_DESIGN
verified = client.post('/api/design/status', json={
    'name': active,
    'status': 'working',
    'note': 'CI physical-verification eligibility contract test',
    'physical_verified': True,
})
assert verified.status_code == 200, verified.text
assert verified.json()['physical_verified'] is True, verified.json()

# Return the metadata to an editable state, then inject a conceptual proxy and prove
# the API refuses to call that model physically verified.
core.set_design_status(active, 'untested', 'proxy regression setup', False)
generic = next(
    c for c in component_registry.all_components()
    if c.get('manufacturer') == 'Generic'
    and component_registry.GEOMETRY_RANK.get(c.get('geometry', {}).get('fidelity', 'none'), 0)
        < component_registry.GEOMETRY_RANK['detailed_parametric']
)
proxy = component_registry.make_project_object(generic['id'])
proxy['id'] = 'api-proxy-regression'
core.PROJECT['objects'].append(proxy)
core.PROJECT.setdefault('bom', []).append(component_registry.bom_item(generic['id'], 1))

blocked_report = client.get('/api/production-readiness')
assert blocked_report.status_code == 200, blocked_report.text
assert blocked_report.json()['ready_for_physical_verification'] is False, blocked_report.json()

blocked = client.post('/api/design/status', json={
    'name': active,
    'status': 'working',
    'note': 'must be rejected',
    'physical_verified': True,
})
assert blocked.status_code == 409, blocked.text
assert 'cannot be marked physically verified' in str(blocked.json()).lower(), blocked.json()

print('ForgeCAD production readiness API: PASS')
