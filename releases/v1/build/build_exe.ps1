param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$V1Dir = Split-Path -Parent $ScriptDir
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $V1Dir)

$DistDir = Join-Path $ScriptDir "dist"
$BuildTemp = Join-Path $ScriptDir "pyinstaller_build"
$WorkDir = Join-Path $BuildTemp "work"
$SpecDir = Join-Path $BuildTemp "spec"
$BackendDir = Join-Path $ProjectRoot "Backend"
$FrontEndDir = Join-Path $ProjectRoot "FrontEnd"
$CompanyFile = Join-Path $ProjectRoot "company.txt"
$RequirementsFile = Join-Path $ProjectRoot "requirements.txt"

if ($Clean) {
    if (Test-Path $DistDir) { Remove-Item $DistDir -Recurse -Force }
    if (Test-Path $BuildTemp) { Remove-Item $BuildTemp -Recurse -Force }
}

New-Item -ItemType Directory -Force -Path $DistDir | Out-Null
New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
New-Item -ItemType Directory -Force -Path $SpecDir | Out-Null

Write-Host "==> Installing/Updating PyInstaller..."
py -3 -m pip install --upgrade pyinstaller | Out-Host

Write-Host "==> Building YouAI executable (onedir)..."
Push-Location $ProjectRoot
try {
    py -3 -m PyInstaller `
        --noconfirm `
        --clean `
        --name "YouAI" `
        --onedir `
        --paths "$ProjectRoot" `
        --add-data "$BackendDir;Backend" `
        --add-data "$FrontEndDir;FrontEnd" `
        --add-data "$CompanyFile;." `
        --add-data "$RequirementsFile;." `
        --distpath "$DistDir" `
        --workpath "$WorkDir" `
        --specpath "$SpecDir" `
        "Start.py"
}
finally {
    Pop-Location
}

$ExePath = Join-Path $DistDir "YouAI\YouAI.exe"
if (-not (Test-Path $ExePath)) {
    throw "Build failed: executable not found at $ExePath"
}

Write-Host ""
Write-Host "Build complete."
Write-Host "Executable: $ExePath"
