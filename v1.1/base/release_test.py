from pathlib import Path
import ast
R=Path(__file__).resolve().parent
required=['core.py','analysis.py','agents.py','components.py','software.py','jarvis_bridge.py','server.py','desktop.py','static/index.html','static/app.js','static/styles.css','static/vendor/three.module.js','static/vendor/three.core.js','static/vendor/addons/controls/OrbitControls.js','static/vendor/addons/controls/TransformControls.js','windows/installer.iss']
missing=[x for x in required if not (R/x).exists()]
if missing:raise SystemExit('Missing release files: '+', '.join(missing))
for p in R.glob('*.py'):ast.parse(p.read_text(),filename=str(p))
print('ForgeCAD release preflight: PASS')
