$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r windows/requirements-build.txt
python prepare_frontend.py
python -m compileall -q .
python smoke_test.py
python v1_test.py
python release_test.py
python -m PyInstaller --noconfirm --clean forgecad.spec
& "dist\ForgeCAD\ForgeCAD.exe" --self-test
$ISCC = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
if (-not $ISCC) {
  $Candidates = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "${env:ProgramFiles}\Inno Setup 6\ISCC.exe")
  $ISCC = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $ISCC) { throw "Inno Setup compiler not found" }
& $ISCC "windows\installer.iss"
Write-Host "Windows release complete."
