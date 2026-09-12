$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $PSScriptRoot
$Setup = Join-Path $Root "dist\installer\ForgeCAD-Setup.exe"
if (-not (Test-Path -LiteralPath $Setup -PathType Leaf)) {
    throw "Installer missing: $Setup"
}
$Setup = (Resolve-Path -LiteralPath $Setup).Path

# Use an explicit, isolated install root so CI never depends on LocalAppData,
# Inno Setup's default directory, or a previous ForgeCAD installation.
$TempRoot = $env:RUNNER_TEMP
if ([string]::IsNullOrWhiteSpace($TempRoot)) {
    $TempRoot = [IO.Path]::GetTempPath()
}
$Target = Join-Path $TempRoot "ForgeCAD-v1.1.1-installed"
$InstallLog = Join-Path $TempRoot "ForgeCAD-v1.1.1-install.log"
$SelfTestOut = Join-Path $TempRoot "ForgeCAD-v1.1.1-selftest.stdout.log"
$SelfTestErr = Join-Path $TempRoot "ForgeCAD-v1.1.1-selftest.stderr.log"

if (Test-Path -LiteralPath $Target) {
    Remove-Item -LiteralPath $Target -Recurse -Force
}
New-Item -ItemType Directory -Path $Target -Force | Out-Null
foreach ($Log in @($InstallLog, $SelfTestOut, $SelfTestErr)) {
    if (Test-Path -LiteralPath $Log) { Remove-Item -LiteralPath $Log -Force }
}

Write-Host "Installing candidate from: $Setup"
Write-Host "CI install directory: $Target"
$InstallArgs = @(
    '/VERYSILENT',
    '/SUPPRESSMSGBOXES',
    '/NORESTART',
    '/SP-',
    "/DIR=`"$Target`"",
    "/LOG=`"$InstallLog`""
)
$Install = Start-Process -FilePath $Setup -ArgumentList $InstallArgs -Wait -PassThru
if ($Install.ExitCode -ne 0) {
    if (Test-Path -LiteralPath $InstallLog) {
        Write-Host "----- Inno Setup install log -----"
        Get-Content -LiteralPath $InstallLog | Write-Host
        Write-Host "----- end install log -----"
    }
    throw "Installer returned exit code $($Install.ExitCode)"
}

# Do not assume an exact directory layout. PyInstaller one-dir payloads place
# support files under _internal, while Inno Setup is free to add directories.
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

# ForgeCAD is deliberately built as a Windows GUI subsystem executable
# (PyInstaller console=False). PowerShell's direct '& exe' invocation does not
# reliably wait for GUI applications and can leave $LASTEXITCODE unset. Use a
# real process handle, wait for termination, and inspect Process.ExitCode.
$SelfTest = Start-Process -FilePath $Exe -ArgumentList @('--self-test') -WorkingDirectory $ExeDir -RedirectStandardOutput $SelfTestOut -RedirectStandardError $SelfTestErr -Wait -PassThru
if (Test-Path -LiteralPath $SelfTestOut) {
    $OutText = Get-Content -LiteralPath $SelfTestOut -Raw
    if (-not [string]::IsNullOrWhiteSpace($OutText)) { Write-Host $OutText }
}
if (Test-Path -LiteralPath $SelfTestErr) {
    $ErrText = Get-Content -LiteralPath $SelfTestErr -Raw
    if (-not [string]::IsNullOrWhiteSpace($ErrText)) { Write-Host $ErrText }
}
if ($SelfTest.ExitCode -ne 0) {
    throw "Installed application self-test returned exit code $($SelfTest.ExitCode)"
}
Write-Host "Installed ForgeCAD self-test passed."

# Qualify the installed payload, not merely the pre-installer dist directory.
$RequiredAssets = @(
    @{ Name = 'raspberry_pi_5_official.step'; MinimumBytes = 1000000 },
    @{ Name = 'raspberry_pi_4_model_b_parametric.step'; MinimumBytes = 100000 },
    @{ Name = 'pololu_d24v50f5_official.step'; MinimumBytes = 1000000 }
)
foreach ($Required in $RequiredAssets) {
    $Matches = @(Get-ChildItem -LiteralPath $Target -Filter $Required.Name -File -Recurse)
    if ($Matches.Count -ne 1) {
        throw "Expected exactly one installed $($Required.Name); found $($Matches.Count)"
    }
    if ($Matches[0].Length -lt $Required.MinimumBytes) {
        throw "Installed $($Required.Name) is implausibly small: $($Matches[0].Length) bytes"
    }
    Write-Host "Verified installed authoritative CAD: $($Required.Name) ($($Matches[0].Length) bytes)"
}

# Validate that the installer generated a usable uninstaller and clean up the
# isolated installation. Keep this separate from the application self-test so
# uninstall behavior cannot hide an application qualification failure.
$Uninstallers = @(Get-ChildItem -LiteralPath $Target -Filter 'unins*.exe' -File -Recurse)
if ($Uninstallers.Count -eq 0) {
    throw "Installed candidate did not contain an Inno Setup uninstaller"
}
$Uninstall = Start-Process -FilePath $Uninstallers[0].FullName -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART') -Wait -PassThru
if ($Uninstall.ExitCode -ne 0) {
    throw "Uninstaller returned exit code $($Uninstall.ExitCode)"
}

Write-Host "Windows installed-candidate qualification passed."
