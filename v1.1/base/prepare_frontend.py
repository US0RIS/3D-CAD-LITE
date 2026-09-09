from __future__ import annotations
import os, shutil, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent;V=ROOT/"static"/"vendor";A=V/"addons"/"controls";V.mkdir(parents=True,exist_ok=True);A.mkdir(parents=True,exist_ok=True)
VERSION="0.185.0"
FILES={
 V/"three.module.js":[f"https://cdn.jsdelivr.net/npm/three@{VERSION}/build/three.module.js",f"https://unpkg.com/three@{VERSION}/build/three.module.js"],
 V/"three.core.js":[f"https://cdn.jsdelivr.net/npm/three@{VERSION}/build/three.core.js",f"https://unpkg.com/three@{VERSION}/build/three.core.js"],
 A/"OrbitControls.js":[f"https://cdn.jsdelivr.net/npm/three@{VERSION}/examples/jsm/controls/OrbitControls.js",f"https://unpkg.com/three@{VERSION}/examples/jsm/controls/OrbitControls.js"],
 A/"TransformControls.js":[f"https://cdn.jsdelivr.net/npm/three@{VERSION}/examples/jsm/controls/TransformControls.js",f"https://unpkg.com/three@{VERSION}/examples/jsm/controls/TransformControls.js"],
}

def download(path,urls):
    if path.exists() and path.stat().st_size>1000:return
    last=None
    for u in urls:
        try:
            req=urllib.request.Request(u,headers={"User-Agent":"ForgeCAD/1.0"})
            with urllib.request.urlopen(req,timeout=30) as r:data=r.read()
            if len(data)<1000:raise RuntimeError(f"unexpectedly small response from {u}")
            path.write_bytes(data);print(f"Prepared {path.relative_to(ROOT)} ({len(data)} bytes)");return
        except Exception as e:last=e
    raise RuntimeError(f"Could not download {path.name}: {last}")
def main():
    for p,u in FILES.items():download(p,u)
    print("ForgeCAD frontend runtime is ready.")
if __name__=="__main__":main()
