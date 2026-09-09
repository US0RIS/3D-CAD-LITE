from __future__ import annotations
from pathlib import Path
import sys

root=Path(sys.argv[1] if len(sys.argv)>1 else "v1.1/base")
path=root/"physical_components.py";text=path.read_text(encoding="utf-8")
changes=[
('''if axis=="x":sh=cq.Workplane("YZ").circle(d/2).extrude(h,both=True).val().translate((cx,cy,cz))\n    elif axis=="y":sh=cq.Workplane("XZ").circle(d/2).extrude(h,both=True).val().translate((cx,cy,cz))\n    else:sh=cq.Workplane("XY").circle(d/2).extrude(h,both=True).val().translate((cx,cy,cz))''',
'''# CadQuery ``both=True`` extrudes the requested distance in both directions.\n    # ``h`` is the engineering full length, so use h/2 on each side.\n    half=float(h)/2.0\n    if axis=="x":sh=cq.Workplane("YZ").circle(d/2).extrude(half,both=True).val().translate((cx,cy,cz))\n    elif axis=="y":sh=cq.Workplane("XZ").circle(d/2).extrude(half,both=True).val().translate((cx,cy,cz))\n    else:sh=cq.Workplane("XY").circle(d/2).extrude(half,both=True).val().translate((cx,cy,cz))'''),
('''outer=cq.Workplane("XY").circle(d/2).circle(b/2).extrude(w,both=True).val();shield=cq.Workplane("XY").circle(d*.44).circle(b*.54).extrude(w*.82,both=True).val()''',
'''outer=cq.Workplane("XY").circle(d/2).circle(b/2).extrude(w/2,both=True).val();shield=cq.Workplane("XY").circle(d*.44).circle(b*.54).extrude(w*.41,both=True).val()'''),
]
for old,new in changes:
    if new in text:continue
    if old not in text:raise RuntimeError(f"geometry dimension patch anchor missing: {old[:100]!r}")
    text=text.replace(old,new,1)
path.write_text(text,encoding="utf-8")
print("Corrected ForgeCAD purchased-component full-length geometry semantics")
