from __future__ import annotations
import json, os, shutil, socket, subprocess, sys, threading, time, urllib.request
from pathlib import Path

def app_root():
    if getattr(sys,"frozen",False) and hasattr(sys,"_MEIPASS"):return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent
ROOT=app_root()
def platform_data_dir():
    if sys.platform=="darwin":return Path.home()/"Library"/"Application Support"/"ForgeCAD"
    if sys.platform=="win32":return Path(os.environ.get("LOCALAPPDATA") or (Path.home()/"AppData"/"Local"))/"ForgeCAD"
    return Path(os.environ.get("XDG_DATA_HOME") or (Path.home()/".local"/"share"))/"ForgeCAD"
DATA_DIR=platform_data_dir();DATA_DIR.mkdir(parents=True,exist_ok=True)
os.environ.setdefault("FORGECAD_DATA_DIR",str(DATA_DIR));os.environ.setdefault("FORGECAD_OLLAMA_MODEL","qwen3:8b");os.environ.setdefault("FORGECAD_STRICT_OLLAMA_MODEL","1")
BUILD_ID=f"forgecad-v1.1.1-{sys.platform}-{os.uname().machine if hasattr(os,'uname') else 'x64'}";os.environ["FORGECAD_BUILD_ID"]=BUILD_ID
DISCOVERY_FILE=DATA_DIR/"jarvis_bridge.json"

def free_port(preferred=8765):
    try:
        s=socket.socket();s.bind(("127.0.0.1",preferred));s.close();return preferred
    except OSError:
        s=socket.socket();s.bind(("127.0.0.1",0));p=s.getsockname()[1];s.close();return p

def frontend_preflight():
    req=[ROOT/"static"/"index.html",ROOT/"static"/"app.js",ROOT/"static"/"styles.css",ROOT/"static"/"vendor"/"three.module.js",ROOT/"static"/"vendor"/"three.core.js",ROOT/"static"/"vendor"/"addons"/"controls"/"OrbitControls.js",ROOT/"static"/"vendor"/"addons"/"controls"/"TransformControls.js"]
    missing=[str(p.relative_to(ROOT)) for p in req if not p.exists()]
    if missing:raise RuntimeError("ForgeCAD frontend dependency preflight failed: "+", ".join(missing))

def ollama_alive():
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags",timeout=.7) as r:return r.status==200
    except Exception:return False
def find_ollama():
    exe=shutil.which("ollama")
    if exe:return exe
    candidates=[]
    if sys.platform=="darwin":candidates=[Path("/Applications/Ollama.app/Contents/Resources/ollama"),Path("/opt/homebrew/bin/ollama"),Path("/usr/local/bin/ollama")]
    elif sys.platform=="win32":candidates=[Path(os.environ.get("LOCALAPPDATA",''))/"Programs"/"Ollama"/"ollama.exe",Path(os.environ.get("ProgramFiles",''))/"Ollama"/"ollama.exe"]
    return next((str(x) for x in candidates if x.exists()),None)
def ensure_ollama():
    if ollama_alive():return
    exe=find_ollama()
    if not exe:return
    kw={"stdout":subprocess.DEVNULL,"stderr":subprocess.DEVNULL,"stdin":subprocess.DEVNULL}
    if sys.platform=="win32":kw["creationflags"]=getattr(subprocess,"CREATE_NO_WINDOW",0)
    else:kw["start_new_session"]=True
    try:
        subprocess.Popen([exe,"serve"],**kw);deadline=time.time()+6
        while time.time()<deadline:
            if ollama_alive():return
            time.sleep(.2)
    except Exception:pass
def warm_model():
    def worker():
        if not ollama_alive():return
        try:
            body=json.dumps({"model":os.environ["FORGECAD_OLLAMA_MODEL"],"stream":False,"keep_alive":"30m","prompt":""}).encode();req=urllib.request.Request("http://127.0.0.1:11434/api/generate",data=body,headers={"Content-Type":"application/json"});urllib.request.urlopen(req,timeout=180).read()
        except Exception:pass
    threading.Thread(target=worker,daemon=True,name="ForgeCAD-Ollama-Warmup").start()
def wait_http(url,timeout=60):
    deadline=time.time()+timeout;last=None
    while time.time()<deadline:
        try:
            with urllib.request.urlopen(url,timeout=.7) as r:
                if r.status==200:return
        except Exception as e:last=e
        time.sleep(.1)
    raise RuntimeError(f"ForgeCAD backend did not start: {last}")
def start_embedded():
    import uvicorn, jarvis_bridge, server
    port=free_port();url=f"http://127.0.0.1:{port}";jarvis_bridge.write_discovery(url);cfg=uvicorn.Config(server.app,host="127.0.0.1",port=port,log_level="warning",access_log=False);inst=uvicorn.Server(cfg)
    threading.Thread(target=inst.run,daemon=True,name="ForgeCAD-Engine").start();wait_http(url+"/api/health");return url
def run_headless():
    import uvicorn,jarvis_bridge,server
    ensure_ollama();port=free_port();url=f"http://127.0.0.1:{port}";jarvis_bridge.write_discovery(url);uvicorn.run(server.app,host="127.0.0.1",port=port,log_level="warning",access_log=False);return 0

def self_test():
    # Frozen GUI applications do not have a console on Windows, and native CAD
    # failures can terminate the process before a Python traceback exists. Keep a
    # deterministic on-disk qualification trace and enable faulthandler early.
    trace_path=DATA_DIR/"packaged_self_test.log"
    trace_path.parent.mkdir(parents=True,exist_ok=True)
    trace=open(trace_path,"w",encoding="utf-8",buffering=1)
    def mark(stage,detail=""):
        trace.write(f"{time.time():.3f} {stage}{(': '+detail) if detail else ''}\n");trace.flush()
    try:
        try:
            import faulthandler
            faulthandler.enable(file=trace,all_threads=True)
        except Exception as exc:
            mark("faulthandler-unavailable",repr(exc))
        mark("start",BUILD_ID)
        frontend_preflight();mark("frontend-preflight")
        import cadquery as cq
        mark("cadquery-import",getattr(cq,"__version__","unknown"))
        import core;mark("core-import")
        import components;mark("components-import",str(len(components.REGISTRY)))
        import analysis;mark("analysis-import")
        import server;mark("server-import")
        if len(components.REGISTRY)<200:raise RuntimeError("Component registry incomplete")

        # Exercise the exact OpenCascade paths needed by production: parametric
        # geometry, tessellation, engineering analysis and bundled STEP import.
        obj=core.PROJECT["objects"][0]
        m=core.object_metrics(obj);mark("object-metrics")
        mesh=core.tessellate(obj,.5);mark("tessellation",str(len(mesh.get("triangles",[]))))
        a=analysis.quick_cantilever(obj,100);mark("analysis",str(a.get("yield_fos")))
        assert m["volume_mm3"]>0 and mesh["triangles"] and a["yield_fos"]>0

        step_assets=[
            ("raspberry_pi_5_official.step",80.0,50.0),
            ("pololu_d24v50f5_official.step",15.0,18.0),
        ]
        for filename,min_x,min_y in step_assets:
            path=ROOT/"component_assets"/filename
            if not path.exists():raise RuntimeError(f"Bundled authoritative STEP missing: {filename}")
            shape=cq.importers.importStep(str(path)).val();bb=shape.BoundingBox()
            if bb.xlen<min_x or bb.ylen<min_y or bb.zlen<=0:raise RuntimeError(f"Bundled STEP envelope invalid: {filename}")
            mark("step-import",f"{filename} {bb.xlen:.2f}x{bb.ylen:.2f}x{bb.zlen:.2f}")

        result=json.dumps({"ok":True,"build":BUILD_ID,"component_count":len(components.REGISTRY),"volume_mm3":m["volume_mm3"]})
        mark("pass",result)
        # PyInstaller windowed/GUI builds intentionally have no console on Windows;
        # sys.stdout may therefore be None even when launched with --self-test.
        out=getattr(sys,"stdout",None)
        if out is not None:
            try:out.write(result+"\n");out.flush()
            except Exception:pass
        return 0
    except BaseException as exc:
        mark("python-failure",repr(exc))
        raise
    finally:
        try:trace.flush();trace.close()
        except Exception:pass

def run_ui():
    frontend_preflight();ensure_ollama();base=start_embedded();warm_model();import webview
    webview.create_window("ForgeCAD",url=base+f"/?build={BUILD_ID}",width=1600,height=980,min_size=(1050,680),background_color="#090c10",text_select=True)
    if sys.platform=="darwin":webview.start(gui="cocoa",debug=False,private_mode=False)
    elif sys.platform=="win32":webview.start(gui="edgechromium",debug=False,private_mode=False)
    else:webview.start(debug=False,private_mode=False)
    return 0
def main():
    if "--self-test" in sys.argv:return self_test()
    if "--headless" in sys.argv or "--engine" in sys.argv:return run_headless()
    return run_ui()
if __name__=="__main__":raise SystemExit(main())
