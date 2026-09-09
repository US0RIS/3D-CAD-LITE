$ErrorActionPreference="Stop"
$Root=Split-Path -Parent $PSScriptRoot
$Setup=Join-Path $Root "dist\installer\ForgeCAD-Setup.exe"
if (-not (Test-Path $Setup)) { throw "Installer missing" }
$Target=Join-Path $env:TEMP "ForgeCAD-CI-Install"
if (Test-Path $Target) { Remove-Item $Target -Recurse -Force }
$p=Start-Process -FilePath $Setup -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',"/DIR=$Target") -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "Installer returned $($p.ExitCode)" }
$Exe=Join-Path $Target 'ForgeCAD.exe'
if (-not (Test-Path $Exe)) { throw "Installed executable missing" }
$p2=Start-Process -FilePath $Exe -ArgumentList '--self-test' -Wait -PassThru -NoNewWindow
if ($p2.ExitCode -ne 0) { throw "Installed application self-test returned $($p2.ExitCode)" }
Write-Host "Installed ForgeCAD self-test passed."
