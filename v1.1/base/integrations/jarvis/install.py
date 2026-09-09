from __future__ import annotations
import argparse, shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--jarvis',required=True);a=p.parse_args();root=Path(a.jarvis).expanduser().resolve();src=Path(__file__).with_name('forgecad_tool.py')
if not root.exists():raise SystemExit(f'Jarvis path does not exist: {root}')
dst=root/'jarvis_mrb'/'forgecad_tool.py';dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);print(f'Installed ForgeCAD adapter at {dst}')
