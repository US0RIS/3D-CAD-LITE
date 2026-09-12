$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $PSScriptRoot
$Setup = Join-Path $Root "dist\installer\ForgeCAD-Setup.exe"
if (-not (Test-Path -LiteralPath $Setup -PathType Leaf)) {
    throw "Installer missing: $Setup"
}
$Setup = (Resolve-Path -LiteralPath $Setup).Path

# Use an explicit, isolated install root so the CI test never depends on the
# runner account's LocalAppData, Inno Setup's default directory, or a previous
# ForgeCAD installation.
$Target = Join-Path $env:RUNNER_TEMP "ForgeCAD-v1.1.1-installed"
if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) {
    $Target = Join-Path $env:TEMP "ForgeCAD-v1.1.1-installed"
}
if (Test-Path -LiteralPath $Target) {
    Remove-Item -LiteralPath $Target -Recurse -Force
}
New-Item -ItemType Directory -Path $Target -Force | Out-Null

Write-Host "Installing candidate from: $Setup"
Write-Host "CI install directory: $Target"
$InstallArgs = @(
    '/VERYSILENT',
    '/SUPPRESSMSGBOXES',
    '/NORESTART',
    '/SP-',
    "/DIR=$Target"
)
$Install = Start-Process -FilePath $Setup -ArgumentList $InstallArgs -Wait -PassThru
if ($Install.ExitCode -ne 0) {
    throw "Installer returned exit code $($Install.ExitCode)"
}

# Do not assume the executable is directly at the requested root.  Inno Setup
# configuration can legitimately add a directory level; what matters is that
# the installed payload contains exactly one runnable ForgeCAD executable.
$Executables = @(Get-ChildItem -LiteralPath $Target -Filter 'ForgeCAD.exe' -File -Recurse)
if ($Executables.Count -eq 0) {
    $Tree = (Get-ChildItem -LiteralPath $Target -Recurse | ForEach-Object FullName) -join "`n"
    throw "Installed ForgeCAD.exe was not found under $Target. Installed tree:`n$Tree"
}
if ($Executables.Count -gt 1) {
    throw "Expected one installed ForgeCAD.exe under $Target; found $($Executables.Count): $($Executables.FullName -join ', ')"
}
$Exe = $Executables[0].FullName
$ExeDir = Split-Path -Parent $Exe
Write-Host "Running installed candidate self-test: $Exe"

# Run from the installed application's own directory.  PyInstaller one-dir
# applications may resolve bundled resources relative to the executable/CWD;
# launching from the workflow checkout can make an otherwise valid installed
# package fail only in CI.
Push-Location $ExeDir
try {
    & $Exe '--self-test'
    $SelfTestExit = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($null -eq $SelfTestExit) {
    throw "Installed application self-test did not return an exit code"
}
if ($SelfTestExit -ne 0) {
    throw "Installed application self-test returned exit code $SelfTestExit"
}
Write-Host "Installed ForgeCAD self-test passed."

# Validate that the generated installer also produced a usable uninstaller,
# then remove the test installation to avoid contaminating subsequent jobs.
$Uninstallers = @(Get-ChildItem -LiteralPath $Target -Filter 'unins*.exe' -File)
if ($Uninstallers.Count -gt 0) {
    $Uninstall = Start-Process -FilePath $Uninstallers[0].FullName -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART') -Wait -PassThru
    if ($Uninstall.ExitCode -ne 0) {
        throw "Uninstaller returned exit code $($Uninstall.ExitCode)"
    }
} elseif (Test-Path -LiteralPath $Target) {
    Remove-Item -LiteralPath $Target -Recurse -Force
}

Write-Host "Windows installed-candidate qualification passed."
