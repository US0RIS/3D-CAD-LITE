# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules
from pathlib import Path
import sys

root = Path(SPECPATH)
datas = [
    (str(root / 'static'), 'static'),
    (str(root / 'README.md'), '.'),
    (str(root / 'JARVIS_INTEGRATION.md'), '.'),
    (str(root / 'COMPONENT_REGISTRY.md'), '.'),
    (str(root / 'component_assets'), 'component_assets'),
]
binaries = []
hidden = []

# OCP is a compiled package with a large set of dynamically loaded OpenCascade
# modules, so retain its complete native closure.  The other application/runtime
# packages also rely on dynamic imports and are safe to collect wholesale.
for pkg in ['OCP', 'webview', 'uvicorn', 'fastapi', 'starlette', 'pydantic']:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hidden += h
    except Exception as exc:
        print('collect_all warning', pkg, exc)

# CadQuery 2.8 installs VTK/Trame as optional visualization support. ForgeCAD's
# desktop renderer is Three.js and does not use CadQuery's notebook/VTK stack.
# collect_all('cadquery') used to drag every VTK backend plus Matplotlib/Numba
# into the Windows image; the resulting native DLL closure can crash the frozen
# process before ForgeCAD reaches its own code.  Collect CadQuery's functional
# modules, but deliberately omit those visualization-only entry points.
_cadquery_ignored_prefixes = (
    'cadquery.vis',
    'cadquery.cq_directive',
    'cadquery.occ_impl.jupyter_tools',
    'cadquery.fig',
)
try:
    hidden += [
        name for name in collect_submodules('cadquery')
        if not name.startswith(_cadquery_ignored_prefixes)
    ]
except Exception as exc:
    print('collect_submodules warning', 'cadquery', exc)

# Backends and optional platform integrations are loaded dynamically by pywebview.
hidden += ['multipart', 'python_multipart']
first_party = [
    'agents', 'analysis', 'core', 'components', 'component_registry',
    'component_importers', 'physical_components', 'production_readiness',
    'system_validation', 'project_bundle', 'acceptance_design',
    'assembly_validation', 'mounting', 'software', 'jarvis_bridge',
]
hidden += first_party
if sys.platform == 'darwin':
    hidden += ['webview.platforms.cocoa']
elif sys.platform == 'win32':
    hidden += ['webview.platforms.edgechromium', 'webview.platforms.winforms']
else:
    hidden += ['webview.platforms.gtk']

# These packages are only part of CadQuery's optional notebook/VTK display
# surface.  Excluding them is intentional: ForgeCAD does not call them, and it
# keeps incompatible native visualization DLLs out of the Windows bundle.
optional_visualization_excludes = [
    'tkinter', 'vtk', 'vtkmodules', 'trame', 'trame_client', 'trame_server',
    'trame_vtk', 'trame_vuetify', 'trame_components', 'matplotlib',
    'numba', 'llvmlite',
]

a = Analysis(
    ['desktop.py'],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=optional_visualization_excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ForgeCAD',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='ForgeCAD')
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='ForgeCAD.app',
        icon=None,
        bundle_identifier='com.forgecad.workbench',
        info_plist={
            'CFBundleShortVersionString': '1.1.1',
            'CFBundleVersion': '111',
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '13.0',
        },
    )
