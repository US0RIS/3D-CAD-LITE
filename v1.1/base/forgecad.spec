# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
from pathlib import Path
import sys

root=Path(SPECPATH)
datas=[(str(root/'static'),'static'),(str(root/'README.md'),'.'),(str(root/'JARVIS_INTEGRATION.md'),'.'),(str(root/'COMPONENT_REGISTRY.md'),'.')]
binaries=[];hidden=[]
for pkg in ['cadquery','OCP','vtkmodules','webview','uvicorn','fastapi','starlette','pydantic']:
    try:
        d,b,h=collect_all(pkg);datas+=d;binaries+=b;hidden+=h
    except Exception as e:print('collect_all warning',pkg,e)
# Backends and optional platform integrations are loaded dynamically by pywebview.
hidden += ['multipart','python_multipart']
first_party = ['agents','analysis','core','components','component_registry','component_importers','physical_components','system_validation','project_bundle','acceptance_design','assembly_validation','mounting','software','jarvis_bridge']
hidden += first_party
if sys.platform == 'darwin': hidden += ['webview.platforms.cocoa']
elif sys.platform == 'win32': hidden += ['webview.platforms.edgechromium','webview.platforms.winforms']
else: hidden += ['webview.platforms.gtk']
a=Analysis(['desktop.py'],pathex=[str(root)],binaries=binaries,datas=datas,hiddenimports=hidden,hookspath=[],runtime_hooks=[],excludes=['tkinter'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='ForgeCAD',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False,disable_windowed_traceback=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='ForgeCAD')
if sys.platform=='darwin':
    app=BUNDLE(coll,name='ForgeCAD.app',icon=None,bundle_identifier='com.forgecad.workbench',info_plist={'CFBundleShortVersionString':'1.1.0','CFBundleVersion':'110','NSHighResolutionCapable':True,'LSMinimumSystemVersion':'13.0'})
