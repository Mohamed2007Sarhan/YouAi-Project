param(
    [bool]$BuildExeFirst = $true,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$V1Dir = Split-Path -Parent $ScriptDir
$PackageDir = Join-Path $V1Dir "package"
$IssPath = Join-Path $ScriptDir "YouAI_Setup.iss"
$ExePath = Join-Path $ScriptDir "dist\YouAI\YouAI.exe"

if ($BuildExeFirst) {
    Write-Host "==> Building EXE before setup..."
    & (Join-Path $ScriptDir "build_exe.ps1") -Clean:$Clean
}

if (-not (Test-Path $ExePath)) {
    throw "EXE not found at $ExePath. Run build_exe.ps1 first."
}

New-Item -ItemType Directory -Force -Path $PackageDir | Out-Null

$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) {
    $iscc = "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
}
if (-not (Test-Path $iscc)) {
    throw "Inno Setup compiler not found. Install Inno Setup 6 first."
}

Write-Host "==> Compiling installer with Inno Setup..."
Push-Location $ScriptDir
try {
    & $iscc $IssPath
}
finally {
    Pop-Location
}

$SetupExe = Join-Path $PackageDir "YouAI_v1_Setup.exe"
if (-not (Test-Path $SetupExe)) {
    throw "Setup build failed: $SetupExe not found."
}

Write-Host ""
Write-Host "Setup ready:"
Write-Host $SetupExe
