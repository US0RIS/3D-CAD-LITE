#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)";cd "$ROOT"
VERSION="$(python - <<'PY'
import re
from pathlib import Path
m=re.search(r'^APP_VERSION\s*=\s*"([^"]+)"',Path('core.py').read_text(),re.M)
if not m: raise SystemExit('APP_VERSION not found')
print(m.group(1))
PY
)"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt 'pyinstaller>=6.16,<7' 'httpx>=0.28,<1'
python prepare_component_assets.py
python prepare_frontend.py
python -m compileall -q .
python smoke_test.py
python api_test.py
python acceptance_test.py
python acceptance_api_test.py
python component_fidelity_test.py
python production_readiness_test.py
python v1_test.py
python release_test.py
python -m PyInstaller --noconfirm --clean forgecad.spec
APP="$ROOT/dist/ForgeCAD.app"
if [[ ! -d "$APP" ]]; then echo "ForgeCAD.app missing" >&2; exit 1; fi
codesign --force --deep --sign - "$APP"
"$APP/Contents/MacOS/ForgeCAD" --self-test
mkdir -p "$ROOT/dist/dmg-root";rm -rf "$ROOT/dist/dmg-root/ForgeCAD.app";cp -R "$APP" "$ROOT/dist/dmg-root/ForgeCAD.app";ln -sfn /Applications "$ROOT/dist/dmg-root/Applications"
hdiutil create -volname "ForgeCAD v${VERSION}" -srcfolder "$ROOT/dist/dmg-root" -ov -format UDZO "$ROOT/dist/ForgeCAD-v${VERSION}-macOS-arm64.dmg"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ROOT/dist/ForgeCAD-v${VERSION}-macOS-arm64-app.zip"
echo "macOS ForgeCAD ${VERSION} release candidate complete."
