$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "ForgeCAD Windows 11 build"
Write-Host "========================="

if (-not (Test-Path ".venv\Scripts\python.exe")) {
  python -m venv .venv
  if ($LASTEXITCODE -ne 0) { throw "Python 3.12+ is required to build ForgeCAD." }
}
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r windows\requirements-build.txt
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File windows\prepare_frontend.ps1

if (-not (Test-Path "static\vendor\three.module.js")) { throw "Three.js runtime was not prepared." }
if (-not (Test-Path "static\vendor\rapier.mjs")) { throw "Rapier runtime was not prepared." }

$TestData = Join-Path $env:TEMP ("ForgeCAD-ci-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $TestData | Out-Null
$env:FORGECAD_DATA_DIR = $TestData
try {
  python -m compileall -q .
  python smoke_test.py
  python v1_test.py
  python release_test.py
} finally {
  Remove-Item Env:FORGECAD_DATA_DIR -ErrorAction SilentlyContinue
  Remove-Item $TestData -Recurse -Force -ErrorAction SilentlyContinue
}

pyinstaller --noconfirm --clean forgecad.spec

Write-Host ""
if (Test-Path "dist\ForgeCAD-Windows-x64.zip") { Remove-Item "dist\ForgeCAD-Windows-x64.zip" -Force }
Compress-Archive -Path "dist\ForgeCAD\*" -DestinationPath "dist\ForgeCAD-Windows-x64.zip" -CompressionLevel Optimal

Write-Host "Built: $Root\dist\ForgeCAD\ForgeCAD.exe"
Write-Host "Portable ZIP: $Root\dist\ForgeCAD-Windows-x64.zip"
Write-Host "Projects are stored in %LOCALAPPDATA%\ForgeCAD\projects"
Write-Host ""

$ISCC = @(
  "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
  "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($ISCC) {
  & $ISCC windows\installer.iss
  Write-Host "Installer created under dist\installer."
} else {
  Write-Host "Inno Setup 6 not found; skipping installer. The onedir app is complete and runnable."
}
