#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)";cd "$ROOT"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt 'pyinstaller>=6.16,<7'
python prepare_frontend.py
python -m compileall -q .
python smoke_test.py
python v1_test.py
python release_test.py
python -m PyInstaller --noconfirm --clean forgecad.spec
APP="$ROOT/dist/ForgeCAD.app"
if [[ ! -d "$APP" ]]; then echo "ForgeCAD.app missing" >&2; exit 1; fi
codesign --force --deep --sign - "$APP"
"$APP/Contents/MacOS/ForgeCAD" --self-test
mkdir -p "$ROOT/dist/dmg-root";rm -rf "$ROOT/dist/dmg-root/ForgeCAD.app";cp -R "$APP" "$ROOT/dist/dmg-root/ForgeCAD.app";ln -sfn /Applications "$ROOT/dist/dmg-root/Applications"
hdiutil create -volname "ForgeCAD v1.0.1" -srcfolder "$ROOT/dist/dmg-root" -ov -format UDZO "$ROOT/dist/ForgeCAD-v1.0.1-macOS-arm64.dmg"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ROOT/dist/ForgeCAD-v1.0.1-macOS-arm64-app.zip"
echo "macOS release complete."
