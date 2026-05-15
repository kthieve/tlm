#Requires -Version 5.1
# Install tlm on Windows.
# Default install directory: %LOCALAPPDATA%\tlm (fallback to C:\tlm)
$defaultDest = Join-Path $env:LOCALAPPDATA "tlm"
if (-not $env:LOCALAPPDATA) { $defaultDest = "C:\tlm" }

param(
    [string]$Version = "0.3.0.dev1",
    [string]$Dest    = $defaultDest
)

$ErrorActionPreference = "Stop"

# --- Resolve Python ---------------------------------------------------------
$py = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) {
    Write-Error "Python 3.11+ not found. Install Python from https://python.org first."
    exit 1
}
$pyExe = $py.Source

# --- Source: repo clone or GitHub -------------------------------------------
$repoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$fromClone = Test-Path "$repoRoot\pyproject.toml"

if (-not $fromClone) {
    $Repo = $env:TLM_GITHUB_REPO
    if (-not $Repo) {
        Write-Error "Set env TLM_GITHUB_REPO to your GitHub owner/repo (e.g. myorg/tlm), then re-run."
        exit 1
    }
    $GitRef = if ($env:TLM_GIT_REF) { $env:TLM_GIT_REF } else { "v$Version" }
    $pipSrc = "git+https://github.com/$Repo.git@$GitRef"
} else {
    $pipSrc = $repoRoot
}

# --- Create venv + install ---------------------------------------------------
$venvDir   = Join-Path $Dest "venv"
$venvPy    = Join-Path $venvDir "Scripts\python.exe"
$tlmExe    = Join-Path $venvDir "Scripts\tlm.exe"
$activate  = Join-Path $venvDir "Scripts\activate.bat"

Write-Host "`n=== Installing tlm to $Dest ===`n"

if (-not (Test-Path $venvPy)) {
    Write-Host "Creating virtual environment..."
    & $pyExe -m venv $venvDir
}

Write-Host "Upgrading pip..."
& $venvPy -m pip install -U pip --quiet

Write-Host "Installing tlm..."
if ($fromClone) {
    & $venvPy -m pip install -U --editable $pipSrc --quiet
} else {
    & $venvPy -m pip install -U $pipSrc --quiet
}

# --- Create launcher bat that activates the venv ----------------------------
$batPath = Join-Path $Dest "tlm.bat"
Write-Host "Creating launcher: $batPath"
@"
@echo off
call "$activate"
"$tlmExe" %*
"@ | Set-Content -Path $batPath -Encoding ASCII

# --- Add to user PATH -------------------------------------------------------
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
$dirs = $currentPath -split ";" | ForEach-Object { $_.TrimEnd("\/") } | Where-Object { $_ -ne "" }
$destNorm = $Dest.TrimEnd("\/")

if ($dirs -notcontains $destNorm) {
    $newPath = if ($currentPath) { "$currentPath;$Dest" } else { $Dest }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "`n  Added $Dest to your user PATH."
    Write-Host "  Open a new terminal for PATH changes to take effect."
} else {
    Write-Host "`n  $Dest is already on your PATH."
}

Write-Host "`n=== Done! Run 'tlm init' in a new terminal to get started. ===`n"
