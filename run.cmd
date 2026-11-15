@echo off
rem FIRETRACK launcher for Windows - double-click this file, or run it from any
rem terminal. Batch files are not affected by the PowerShell execution policy,
rem which blocks .ps1 scripts on many machines by default.
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo.
        echo   Python 3.10+ was not found on PATH.
        echo   Install it from https://www.python.org/downloads/ and tick
        echo   "Add python.exe to PATH", then run this file again.
        echo.
        pause
        exit /b 1
    )
    echo   Creating virtual environment ^(one time^)...
    python -m venv .venv
    set "PYTHON=.venv\Scripts\python.exe"
)

"%PYTHON%" -c "import fastapi, uvicorn" >nul 2>nul
if errorlevel 1 (
    echo   Installing FastAPI + uvicorn...
    "%PYTHON%" -m pip install --disable-pip-version-check --quiet -r requirements.txt
    if errorlevel 1 (
        echo.
        echo   Dependency installation failed.
        echo   Run: %PYTHON% -m pip install -r requirements.txt
        pause
        exit /b 1
    )
)

echo.
echo   FIRETRACK  -  Unified Satellite Burning Activity Intelligence Platform
echo   -------------------------------------------------------------------
echo   Starting FIRETRACK. The address is printed on the next line.
echo   Press Ctrl+C to stop.
echo.

"%PYTHON%" -X utf8 run.py
if errorlevel 1 pause
