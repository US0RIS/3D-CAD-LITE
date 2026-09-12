$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$CoreText = Get-Content "core.py" -Raw
$VersionMatch = [regex]::Match($CoreText, '(?m)^APP_VERSION\s*=\s*"([^"]+)"')
if (-not $VersionMatch.Success) { throw "Unable to determine ForgeCAD version from core.py" }
$Version = $VersionMatch.Groups[1].Value

python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r windows/requirements-build.txt "httpx>=0.28,<1"
python prepare_component_assets.py
python prepare_frontend.py
python -m compileall -q .
python smoke_test.py
python api_test.py
python acceptance_test.py
python acceptance_api_test.py
python component_fidelity_test.py
python component_agent_policy_test.py
python production_readiness_test.py
python production_readiness_api_test.py
python v1_test.py
python release_test.py
python -m PyInstaller --noconfirm --clean forgecad.spec

# ForgeCAD is a Windows GUI-subsystem executable (PyInstaller console=False).
# Direct PowerShell invocation does not reliably wait for GUI executables, so
# use Start-Process and require a successful exit from the packaged self-test.
$PackagedExe = Join-Path $Root "dist\ForgeCAD\ForgeCAD.exe"
if (-not (Test-Path -LiteralPath $PackagedExe -PathType Leaf)) {
    throw "Packaged ForgeCAD executable missing: $PackagedExe"
}
$PackagedExe = (Resolve-Path -LiteralPath $PackagedExe).Path
$PackagedDir = Split-Path -Parent $PackagedExe
$TracePath = Join-Path $env:LOCALAPPDATA "ForgeCAD\packaged_self_test.log"
if (Test-Path -LiteralPath $TracePath) { Remove-Item -LiteralPath $TracePath -Force }

$SelfTest = Start-Process -FilePath $PackagedExe -ArgumentList @('--self-test') -WorkingDirectory $PackagedDir -Wait -PassThru
if ($SelfTest.ExitCode -ne 0) {
    Write-Host "--- packaged self-test native trace ---"
    if (Test-Path -LiteralPath $TracePath) {
        Get-Content -LiteralPath $TracePath | ForEach-Object { Write-Host $_ }
    } else {
        Write-Host "No packaged self-test trace was created; failure occurred before self_test() opened its trace."
    }
    Write-Host "--- end packaged self-test native trace ---"
    throw "Packaged ForgeCAD self-test returned exit code $($SelfTest.ExitCode)"
}
if (-not (Test-Path -LiteralPath $TracePath)) {
    throw "Packaged ForgeCAD self-test exited successfully but did not create its qualification trace"
}
$TraceText = Get-Content -LiteralPath $TracePath -Raw
if ($TraceText -notmatch '(?m)\spass:\s') {
    Write-Host $TraceText
    throw "Packaged ForgeCAD self-test did not record a PASS checkpoint"
}
Write-Host "Packaged ForgeCAD self-test passed."
Get-Content -LiteralPath $TracePath | ForEach-Object { Write-Host $_ }

$ISCC = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
if (-not $ISCC) {
  $Candidates = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "${env:ProgramFiles}\Inno Setup 6\ISCC.exe")
  $ISCC = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $ISCC) { throw "Inno Setup compiler not found" }
& $ISCC ("/DMyAppVersion={0}" -f $Version) "windows\installer.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
Write-Host "Windows ForgeCAD $Version release candidate complete."
