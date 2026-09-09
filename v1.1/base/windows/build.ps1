$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$CoreText = Get-Content "core.py" -Raw
$VersionMatch = [regex]::Match($CoreText, '(?m)^APP_VERSION\s*=\s*"([^"]+)"')
if (-not $VersionMatch.Success) { throw "Unable to determine ForgeCAD version from core.py" }
$Version = $VersionMatch.Groups[1].Value
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r windows/requirements-build.txt "httpx>=0.28,<1"
python prepare_frontend.py
python -m compileall -q .
python smoke_test.py
python api_test.py
python acceptance_test.py
python acceptance_api_test.py
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
& $ISCC ("/DMyAppVersion={0}" -f $Version) "windows\installer.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
Write-Host "Windows ForgeCAD $Version release candidate complete."
