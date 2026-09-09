from __future__ import annotations
from pathlib import Path
import sys

root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()

def replace(path:str, old:str, new:str):
    p=root/path
    s=p.read_text(encoding='utf-8')
    if old not in s:
        raise SystemExit(f'v1.0.1 patch anchor not found in {path}: {old[:80]!r}')
    p.write_text(s.replace(old,new),encoding='utf-8')

# Core version/material/default assembly.
replace('core.py','APP_VERSION = "1.0.0"','APP_VERSION = "1.0.1"')
replace('core.py',
'    "pa12": {"name":"PA12 Nylon","density_kg_m3":1010,"youngs_modulus_gpa":1.7,"yield_mpa":45,"poisson":0.39,"thermal_w_mk":0.23,"specific_heat_j_kgk":1700,"color":"#9d9486"},\n',
'    "pa12": {"name":"PA12 Nylon","density_kg_m3":1010,"youngs_modulus_gpa":1.7,"yield_mpa":45,"poisson":0.39,"thermal_w_mk":0.23,"specific_heat_j_kgk":1700,"color":"#9d9486"},\n    "pcb_fr4": {"name":"FR-4 PCB","density_kg_m3":1850,"youngs_modulus_gpa":22.0,"yield_mpa":120,"poisson":0.14,"thermal_w_mk":0.30,"specific_heat_j_kgk":1100,"color":"#187a3b"},\n')

old_default='''        "objects":[
            {"id":base_id,"name":"Base Plate","kind":"box","params":{"x":120.0,"y":80.0,"z":8.0},"material":"aluminum_6061_t6","transform":_transform(),"features":[],"semantic":{"role":"structural_base","tags":["machined","reference"],"description":"Primary structural datum plate."},"visible":True},
            {"id":pi_id,"name":"Raspberry Pi 5","kind":"component","params":{"x":85.0,"y":56.0,"z":17.0},"material":"abs","transform":{"position":[0.0,0.0,18.0],"rotation_deg":[0.0,0.0,0.0],"scale":[1.0,1.0,1.0]},"features":[],"semantic":{"role":"embedded_compute","tags":["electronics","programmable"],"description":"Embedded Linux compute module with an in-project code workspace."},"component_ref":"compute.raspberry_pi_5_8gb","code":{"platform":"python/linux","entrypoint":"main.py","files":{"main.py":"from time import sleep\\n\\n\\ndef main():\\n    print('ForgeCAD device online')\\n    while True:\\n        sleep(1)\\n\\nif __name__ == '__main__':\\n    main()\\n","README.md":"# Raspberry Pi workspace\\n\\nEdit and version device code together with the mechanical design.\\n"}},"visible":True},
        ],
'''
new_default='''        "objects":[
            {"id":base_id,"name":"Raspberry Pi 5 Mounting Plate","kind":"mounting_plate","params":{"x":105.0,"y":76.0,"thickness":3.0,"corner_radius":4.0,"mount_x":58.0,"mount_y":49.0,"mount_hole_diameter":2.7,"standoff_od":6.0,"standoff_height":6.0,"chassis_hole_diameter":4.0},"material":"aluminum_6061_t6","transform":_transform(),"features":[],"semantic":{"role":"structural_base","tags":["machined","reference","raspberry-pi-5","m2.5"],"description":"Machined Raspberry Pi 5 mounting plate with 58 x 49 mm M2.5 standoff pattern and corner chassis holes."},"visible":True},
            {"id":pi_id,"name":"Raspberry Pi 5 8GB","kind":"component","params":{"x":85.0,"y":56.0,"z":17.0},"material":"pcb_fr4","transform":{"position":[0.0,0.0,6.8],"rotation_deg":[0.0,0.0,0.0],"scale":[1.0,1.0,1.0]},"features":[],"semantic":{"role":"embedded_compute","tags":["electronics","programmable","raspberry-pi-5","physical-geometry"],"description":"Raspberry Pi 5 8GB physical-layout model with PCB, mounting holes, I/O connectors, GPIO and major packages.","mechanical_source":"https://datasheets.raspberrypi.com/rpi5/raspberry-pi-5-mechanical-drawing.pdf","geometry_fidelity":"mechanical-envelope-detailed"},"component_ref":"compute.raspberry_pi_5_8gb","code":{"platform":"python/linux","entrypoint":"main.py","files":{"main.py":"from time import sleep\\n\\n\\ndef main():\\n    print('ForgeCAD device online')\\n    while True:\\n        sleep(1)\\n\\nif __name__ == '__main__':\\n    main()\\n","README.md":"# Raspberry Pi workspace\\n\\nEdit and version device code together with the mechanical design.\\n"}},"visible":True},
        ],
'''
replace('core.py',old_default,new_default)

p=root/'core.py'; s=p.read_text(encoding='utf-8')
start=s.index('def _base_shape(obj: dict[str, Any]):')
end=s.index('\ndef _apply_feature',start)
geometry=r'''def _rounded_box_xy(x: float, y: float, z: float, radius: float=0.0, center_z: float=0.0):
    wp=cq.Workplane("XY").workplane(offset=center_z-z/2).box(x,y,z,centered=(True,True,False))
    if radius>0:
        try: wp=wp.edges("|Z").fillet(min(radius,x/2-0.01,y/2-0.01))
        except Exception: pass
    return wp.val()


def _mounting_plate_shape(obj: dict[str, Any]):
    p=obj.get("params") or {}
    x=float(p.get("x",105)); y=float(p.get("y",76)); t=float(p.get("thickness",3)); r=float(p.get("corner_radius",4))
    mx=float(p.get("mount_x",58)); my=float(p.get("mount_y",49)); hd=float(p.get("mount_hole_diameter",2.7)); sod=float(p.get("standoff_od",6)); sh=float(p.get("standoff_height",6)); chd=float(p.get("chassis_hole_diameter",4))
    plate=_rounded_box_xy(x,y,t,r,center_z=-t/2)
    mount_pts=[(-mx/2,-my/2),(mx/2,-my/2),(mx/2,my/2),(-mx/2,my/2)]
    standoffs=[]
    for px,py in mount_pts:
        st=cq.Workplane("XY").center(px,py).circle(sod/2).circle(hd/2).extrude(sh).val(); standoffs.append(st)
    shape=cq.Compound.makeCompound([plate,*standoffs])
    for px,py in mount_pts:
        tool=cq.Workplane("XY").workplane(offset=-t-0.5).center(px,py).circle(hd/2).extrude(t+sh+1).val(); shape=shape.cut(tool)
    for px,py in [(-x/2+8,-y/2+8),(x/2-8,-y/2+8),(x/2-8,y/2-8),(-x/2+8,y/2-8)]:
        tool=cq.Workplane("XY").workplane(offset=-t-0.5).center(px,py).circle(chd/2).extrude(t+1).val(); shape=shape.cut(tool)
    return shape


def _pi5_local_parts() -> list[tuple[Any,str]]:
    # Board and mounting data follow Raspberry Pi's published Pi 5 mechanical drawing.
    parts=[]
    board=_rounded_box_xy(85,56,1.6,3,0)
    for px,py in [(-29,-24.5),(29,-24.5),(29,24.5),(-29,24.5)]:
        tool=cq.Workplane("XY").workplane(offset=-1).center(px,py).circle(1.35).extrude(2).val(); board=board.cut(tool)
    parts.append((board,"#16813e"))
    parts += [
        (_rounded_box_xy(17.2,17.2,1.7,0.6,1.65).translate((-8,-1,0)),"#202327"),
        (_rounded_box_xy(12.5,12.5,1.4,0.4,1.5).translate((11,2,0)),"#24272b"),
        (_rounded_box_xy(7,7,1.2,0.3,1.4).translate((-20,11,0)),"#2a2d31"),
        (_rounded_box_xy(8,6,1.1,0.2,1.35).translate((19,-12,0)),"#303338"),
        (_rounded_box_xy(19,17,13.5,0.8,7.55).translate((42.5,-16.5,0)),"#aeb5bc"),
        (_rounded_box_xy(17,14,15.2,0.8,8.4).translate((43.5,3.0,0)),"#aab2ba"),
        (_rounded_box_xy(17,14,15.2,0.8,8.4).translate((43.5,19.0,0)),"#aab2ba"),
        (_rounded_box_xy(9.2,8.0,3.4,1.2,2.5).translate((-31,-29.3,0)),"#b9bec4"),
        (_rounded_box_xy(7.6,7.2,3.2,0.8,2.4).translate((-14,-29.0,0)),"#b8bdc3"),
        (_rounded_box_xy(7.6,7.2,3.2,0.8,2.4).translate((-2,-29.0,0)),"#b8bdc3"),
        (_rounded_box_xy(15,13,1.7,0.4,-1.65).translate((-35,1,0)),"#9da5ac"),
    ]
    parts.append((_rounded_box_xy(51.0,5.2,2.5,0.3,2.05).translate((-5.0,24.2,0)),"#17191b"))
    pins=[]; x0=-29.13
    for col in range(20):
        for row in range(2):
            px=x0+col*2.54; py=22.93+row*2.54
            pins.append(_rounded_box_xy(0.65,0.65,8.0,0,5.3).translate((px,py,0)))
    parts.append((cq.Compound.makeCompound(pins),"#d7a928"))
    parts += [
        (_rounded_box_xy(17,3.8,3.1,0.3,2.35).translate((17.5,-23.5,0)),"#e2ded4"),
        (_rounded_box_xy(17,3.8,3.1,0.3,2.35).translate((17.5,15.5,0)),"#e2ded4"),
        (_rounded_box_xy(11,3.5,2.8,0.3,2.2).translate((-30,22,0)),"#e2ded4"),
        (_rounded_box_xy(6,4,3.3,0.5,2.45).translate((25,23,0)),"#eee9df"),
        (_rounded_box_xy(4.5,4.5,2.8,0.4,2.2).translate((-39,18,0)),"#d9dde0"),
    ]
    return parts


def _component_parts(obj: dict[str, Any]) -> list[tuple[Any,str]]|None:
    if obj.get("component_ref")=="compute.raspberry_pi_5_8gb": return _pi5_local_parts()
    return None


def _base_shape(obj: dict[str, Any]):
    p=obj.get("params") or {}; kind=obj.get("kind","box")
    if kind=="mounting_plate": return _mounting_plate_shape(obj)
    if kind=="component":
        parts=_component_parts(obj)
        if parts: return cq.Compound.makeCompound([sh for sh,_ in parts])
        return cq.Workplane("XY").box(float(p.get("x",20)),float(p.get("y",20)),float(p.get("z",20))).val()
    if kind=="box": return cq.Workplane("XY").box(float(p.get("x",20)),float(p.get("y",20)),float(p.get("z",20))).val()
    if kind=="cylinder": return cq.Workplane("XY").circle(float(p.get("radius",10))).extrude(float(p.get("height",20)),both=True).val()
    if kind=="sphere": return cq.Workplane("XY").sphere(float(p.get("radius",10))).val()
    if kind=="sketch_extrude":
        h=float(p.get("height",10)); sk=p.get("sketch") or {}; typ=sk.get("type","rectangle"); wp=cq.Workplane("XY")
        if typ=="circle": wp=wp.circle(float(sk.get("radius",10)))
        elif typ=="polygon": wp=wp.polyline([(float(a),float(b)) for a,b in sk.get("points",[[-10,-10],[10,-10],[10,10],[-10,10]])]).close()
        else: wp=wp.rect(float(sk.get("width",20)),float(sk.get("height",20)))
        return wp.extrude(h,both=True).val()
    if kind=="revolve":
        pts=[(float(a),float(b)) for a,b in p.get("points",[[0,0],[10,0],[10,20],[0,20]])]
        return cq.Workplane("XZ").polyline(pts).close().revolve(float(p.get("angle_deg",360)),(0,0),(0,1)).val()
    if kind=="step":
        path=Path(str(p.get("path","")))
        if not path.exists(): raise FileNotFoundError(path)
        return cq.importers.importStep(str(path)).val()
    raise ValueError(f"Unsupported kind: {kind}")
'''
s=s[:start]+geometry+s[end:]
p.write_text(s,encoding='utf-8')

replace('core.py',
'''def tessellate(obj: dict[str, Any], tolerance: float=.35) -> dict[str, Any]:
    sh=build_shape(obj); verts,tris=sh.tessellate(float(tolerance)); positions=[[v.x,v.y,v.z] for v in verts]; indices=[list(map(int,t)) for t in tris]
    return {"id":obj["id"],"positions":positions,"triangles":indices,"material":obj.get("material"),"color":MATERIALS.get(obj.get("material"),{}).get("color","#8aa0b6")}
''',
'''def tessellate(obj: dict[str, Any], tolerance: float=.35) -> dict[str, Any]:
    parts=_component_parts(obj) if obj.get("kind")=="component" else None
    if parts and not obj.get("features"):
        t=obj.get("transform") or {}; pos=t.get("position",[0,0,0]); rot=t.get("rotation_deg",[0,0,0]); scl=t.get("scale",[1,1,1]); positions=[]; indices=[]; tri_colors=[]; offset=0
        for sh,color in parts:
            if len({round(float(x),9) for x in scl})==1 and abs(float(scl[0])-1)>1e-9: sh=sh.scale(float(scl[0]))
            if float(rot[0]): sh=sh.rotate((0,0,0),(1,0,0),float(rot[0]))
            if float(rot[1]): sh=sh.rotate((0,0,0),(0,1,0),float(rot[1]))
            if float(rot[2]): sh=sh.rotate((0,0,0),(0,0,1),float(rot[2]))
            sh=sh.translate(tuple(float(v) for v in pos)); verts,tris=sh.tessellate(float(tolerance)); positions.extend([[v.x,v.y,v.z] for v in verts]); indices.extend([[int(a)+offset,int(b)+offset,int(c)+offset] for a,b,c in tris]); tri_colors.extend([color]*len(tris)); offset+=len(verts)
        return {"id":obj["id"],"positions":positions,"triangles":indices,"triangle_colors":tri_colors,"material":obj.get("material"),"color":"#ffffff","geometry_fidelity":"component-specific"}
    sh=build_shape(obj); verts,tris=sh.tessellate(float(tolerance)); positions=[[v.x,v.y,v.z] for v in verts]; indices=[list(map(int,t)) for t in tris]
    return {"id":obj["id"],"positions":positions,"triangles":indices,"material":obj.get("material"),"color":MATERIALS.get(obj.get("material"),{}).get("color","#8aa0b6")}
''')

replace('components.py',
'add("compute.raspberry_pi_5_8gb","compute","Raspberry Pi","5 8GB",dimensions_mm=[85,56,17],mass_g=46,power_w=12,voltage_v=5,programmable=True,code_platform="python/linux",tags=["sbc","linux","gpio"])',
'add("compute.raspberry_pi_5_8gb","compute","Raspberry Pi","5 8GB",dimensions_mm=[85,56,17],mass_g=46,power_w=12,voltage_v=5,programmable=True,code_platform="python/linux",material="pcb_fr4",geometry_profile="raspberry_pi_5",mounting_pattern_mm=[58,49],mount_hole_diameter_mm=2.7,mechanical_source="https://datasheets.raspberrypi.com/rpi5/raspberry-pi-5-mechanical-drawing.pdf",official_step_available=True,tags=["sbc","linux","gpio","physical-cad"])')
replace('server.py',
'args={"name":c["name"],"kind":"component","params":{"x":float(dims[0]),"y":float(dims[1]),"z":float(dims[2])},"material":"abs","component_ref":c["id"],"semantic":{"role":c.get("category"),"tags":c.get("tags",[]),"component":c}}',
'args={"name":c["name"],"kind":"component","params":{"x":float(dims[0]),"y":float(dims[1]),"z":float(dims[2])},"material":c.get("material","abs"),"component_ref":c["id"],"semantic":{"role":c.get("category"),"tags":c.get("tags",[]),"component":c,"geometry_fidelity":"component-specific" if c.get("geometry_profile") else "envelope-proxy"}}')
replace('static/app.js',
"const g=new THREE.BufferGeometry();const pos=[];for(const tri of data.triangles){for(const idx of tri)pos.push(...data.positions[idx])}g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));g.computeVertexNormals();const mat=new THREE.MeshStandardMaterial({color:data.color||0x8aa0b6,metalness:o.kind==='component'?.05:.55,roughness:o.kind==='component'?.65:.35});m=new THREE.Mesh(g,mat);",
"const g=new THREE.BufferGeometry();const pos=[],cols=[];for(let ti=0;ti<data.triangles.length;ti++){const tri=data.triangles[ti],tc=data.triangle_colors?.[ti];const cc=tc?new THREE.Color(tc):null;for(const idx of tri){pos.push(...data.positions[idx]);if(cc)cols.push(cc.r,cc.g,cc.b)}}g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));if(cols.length===pos.length)g.setAttribute('color',new THREE.Float32BufferAttribute(cols,3));g.computeVertexNormals();const mat=new THREE.MeshStandardMaterial({color:cols.length===pos.length?0xffffff:(data.color||0x8aa0b6),vertexColors:cols.length===pos.length,metalness:o.kind==='component'?.12:.55,roughness:o.kind==='component'?.58:.35});m=new THREE.Mesh(g,mat);")

# Modernize regression around the richer default assembly while retaining exact primitive checks.
p=root/'smoke_test.py'; s=p.read_text(encoding='utf-8'); a=s.index('core.reset_project();'); b=s.index("print('ForgeCAD smoke test",a)
body='''core.reset_project();plate=core.PROJECT['objects'][0];pm=core.object_metrics(plate);check(abs(pm['bounds_mm']['x']-105)<1e-6 and abs(pm['bounds_mm']['y']-76)<1e-6,'mounting plate envelope');check(abs(pm['bounds_mm']['z']-9)<1e-6,'plate includes standoffs')
pi=next(o for o in core.PROJECT['objects'] if o.get('component_ref')=='compute.raspberry_pi_5_8gb');pim=core.object_metrics(pi);mesh=core.tessellate(pi,.8);check(pim['bounds_mm']['x']>85 and pim['bounds_mm']['y']>56,'Pi connector envelopes protrude beyond PCB');check(len(mesh.get('triangle_colors',[]))==len(mesh['triangles']) and len(mesh['triangles'])>500,'Pi detailed colored tessellation')
box={'id':'smoke-box','name':'Smoke Box','kind':'box','params':{'x':120.0,'y':80.0,'z':8.0},'material':'aluminum_6061_t6','transform':{'position':[0,0,0],'rotation_deg':[0,0,0],'scale':[1,1,1]},'features':[],'semantic':{},'visible':True};m=core.object_metrics(box);check(abs(m['volume_mm3']-120*80*8)<1e-5,'exact box volume');pre=m['volume_mm3'];box['features']=[{'type':'hole','diameter':10,'axis':'z'}];post=core.object_metrics(box)['volume_mm3'];check(post<pre,'hole subtracts volume');check(len(core.tessellate(box,.5)['triangles'])>10,'tessellation')
check(len(components.REGISTRY)>=200,'expanded component registry');r=components.search_components('raspberry pi',limit=5);check(any('Raspberry Pi' in x['name'] for x in r['results']),'real component search');check(components.component_by_id('compute.raspberry_pi_5_8gb').get('geometry_profile')=='raspberry_pi_5','Pi geometry profile registered')
core.set_design_status(core.ACTIVE_DESIGN,'working_in_real_life','bench verified',True);source=core.ACTIVE_DESIGN;core.execute('add',{'kind':'box','name':'Experiment','params':{'x':10,'y':10,'z':10}},'test','protected mutation');check(core.ACTIVE_DESIGN!=source,'protected baseline auto-branches')
pi=next(o for o in core.PROJECT['objects'] if o.get('code'));core.execute('code_write',{'id':pi['id'],'path':'control.py','content':'def control():\\n    return 1\\n'},'test','code IDE');check(software.validate_workspace(core.PROJECT,pi['id'])['ok'],'code validates')
check(analysis.quick_cantilever(box,100)['yield_fos']>0,'structural');check(analysis.modal_analysis(box)['modes'][0]['frequency_hz']>0,'modal');check(analysis.thermal_analysis(box)['max_temperature_c']>22,'thermal')
path=Path(_tmp.name)/'test.step';cq.exporters.export(core.build_shape(box),str(path),exportType='STEP');check(path.stat().st_size>100,'STEP export');before=len(core.PROJECT['objects']);core.import_step_bytes('roundtrip.step',path.read_bytes());check(len(core.PROJECT['objects'])==before+1,'STEP import')
'''
p.write_text(s[:a]+body+s[b:],encoding='utf-8')

replace('forgecad.spec',"'CFBundleShortVersionString':'1.0.0','CFBundleVersion':'100'","'CFBundleShortVersionString':'1.0.1','CFBundleVersion':'101'")
replace('windows/installer.iss','#define MyAppVersion "1.0.0"','#define MyAppVersion "1.0.1"')
replace('macos/build.sh','ForgeCAD-v1-macOS-arm64.dmg','ForgeCAD-v1.0.1-macOS-arm64.dmg')
replace('macos/build.sh','ForgeCAD-v1-macOS-arm64-app.zip','ForgeCAD-v1.0.1-macOS-arm64-app.zip')
replace('macos/build.sh','ForgeCAD v1"','ForgeCAD v1.0.1"')

# The portable Windows ZIP is not part of the installer release and caused a transient file-lock race.
p=root/'windows/build.ps1'; lines=p.read_text(encoding='utf-8').splitlines(); p.write_text('\n'.join(x for x in lines if 'ForgeCAD-Windows-x64.zip' not in x and 'Compress-Archive' not in x)+'\n',encoding='utf-8')

print('ForgeCAD v1.0.1 geometry patch applied to',root)
