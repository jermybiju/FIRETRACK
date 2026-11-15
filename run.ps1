# FIRETRACK launcher (Windows PowerShell)
#
#   .\run.ps1                start on http://127.0.0.1:8000
#   .\run.ps1 -Port 9000     start on another port
#   .\run.ps1 -OpenBrowser   start and open the interface
#
# On first run this creates a local virtual environment, installs two packages
# (FastAPI + uvicorn) and builds the hotspot database from the bundled NASA
# FIRMS snapshot. Nothing else is required.

param(
    [int]$Port = 8000,
    [switch]$OpenBrowser,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host ""
Write-Host "  FIRETRACK" -ForegroundColor Yellow -NoNewline
Write-Host "  Unified Satellite Burning Activity Intelligence Platform"
Write-Host "  -------------------------------------------------------"

# --- locate Python ---------------------------------------------------------
$python = $null
foreach ($candidate in @("python", "python3", "py")) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) {
        try {
            & $cmd.Source -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) { $python = $cmd.Source; break }
        } catch { }
    }
}
if (-not $python) {
    Write-Host "  Python 3.10+ was not found on PATH." -ForegroundColor Red
    Write-Host "  Install it from https://www.python.org/downloads/ and tick 'Add python.exe to PATH'."
    exit 1
}
Write-Host "  Python: $python"

# --- dependencies ----------------------------------------------------------
# A pre-installed dependency folder (.pydeps) lets the app run in restricted
# environments without any network access.
$prebuilt = Join-Path $PSScriptRoot ".pydeps"
$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not $SkipInstall) {
    if (Test-Path $venvPy) {
        Write-Host "  Virtual environment: .venv"
    } elseif (Test-Path (Join-Path $prebuilt "fastapi")) {
        Write-Host "  Using bundled dependencies: .pydeps"
        $venvPy = $python
    } else {
        Write-Host "  Creating virtual environment (one time)..."
        & $python -m venv .venv
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPy)) {
            Write-Host "  Could not create .venv - falling back to the system Python." -ForegroundColor Yellow
            $venvPy = $python
        }
    }

    & $venvPy -c "import fastapi, uvicorn" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Installing FastAPI + uvicorn..."
        & $venvPy -m pip install --disable-pip-version-check --quiet --upgrade pip
        & $venvPy -m pip install --disable-pip-version-check --quiet -r requirements.txt
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  Dependency installation failed. Run: $venvPy -m pip install -r requirements.txt" -ForegroundColor Red
            exit 1
        }
    }
} else {
    if (Test-Path $venvPy) { } elseif (Test-Path (Join-Path $prebuilt "fastapi")) { $venvPy = $python } else { $venvPy = $python }
}

# --- launch ----------------------------------------------------------------
$env:PYTHONPATH = (Join-Path $PSScriptRoot "backend")
if (Test-Path $prebuilt) {
    $env:PYTHONPATH = "$prebuilt;$env:PYTHONPATH"
}

if (-not (Test-Path (Join-Path $PSScriptRoot "frontend\dist\index.html"))) {
    Write-Host "  Note: frontend/dist is missing. The API will run, but the web UI needs 'pnpm build' in frontend/." -ForegroundColor Yellow
}

$url = "http://127.0.0.1:$Port"
Write-Host "  Starting server on $url" -ForegroundColor Green
Write-Host "  Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

if ($OpenBrowser) {
    Start-Job -ScriptBlock {
        param($u)
        Start-Sleep -Seconds 3
        Start-Process $u
    } -ArgumentList $url | Out-Null
}

& $venvPy -X utf8 run.py --port $Port
