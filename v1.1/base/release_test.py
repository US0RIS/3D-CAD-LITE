from pathlib import Path
import ast
R=Path(__file__).resolve().parent
required=['core.py','analysis.py','agents.py','components.py','software.py','jarvis_bridge.py','server.py','desktop.py','static/index.html','static/app.js','static/styles.css','static/vendor/three.module.js','static/vendor/three.core.js','static/vendor/addons/controls/OrbitControls.js','static/vendor/addons/controls/TransformControls.js','windows/installer.iss']
missing=[x for x in required if not (R/x).exists()]
if missing:raise SystemExit('Missing release files: '+', '.join(missing))
for p in R.glob('*.py'):ast.parse(p.read_text(),filename=str(p))
# Stable-release version contract: prevent installer/application metadata drift.
core_text=(R/'core.py').read_text(encoding='utf-8')
if 'APP_VERSION = "1.1.1"' not in core_text:raise SystemExit('core.APP_VERSION is not stable 1.1.1')
desktop_text=(R/'desktop.py').read_text(encoding='utf-8')
if 'forgecad-v1.1.1-' not in desktop_text:raise SystemExit('desktop build ID is not v1.1.1')
spec_text=(R/'forgecad.spec').read_text(encoding='utf-8')
for token in ["'CFBundleShortVersionString':'1.1.1'", "'CFBundleVersion':'111'", "'agents'"]:
    if token not in spec_text:raise SystemExit('forgecad.spec release contract missing '+token)
installer_text=(R/'windows'/'installer.iss').read_text(encoding='utf-8')
if '#define MyAppVersion "1.1.1"' not in installer_text:raise SystemExit('Windows installer fallback version is not 1.1.1')
print('ForgeCAD release preflight: PASS')
