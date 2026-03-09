@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  where python >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] Python not found in PATH. Please install Python 3.10+ first.
    pause
    exit /b 1
  )
  echo [INFO] Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
  )
)

set PYTHON=.venv\Scripts\python.exe

echo [INFO] Installing dependencies...
"%PYTHON%" -m pip install --disable-pip-version-check -r requirements-lock.txt
if errorlevel 1 (
  echo [ERROR] Failed to install dependencies.
  pause
  exit /b 1
)

if not exist "config\app.yaml" (
  if exist "config\app.json" (
    echo [INFO] Migrating config\app.json to config\app.yaml...
    copy /Y "config\app.json" "config\app.yaml" >nul
  ) else if exist "config\default.yaml" (
    echo [INFO] Creating config\app.yaml from default template...
    copy /Y "config\default.yaml" "config\app.yaml" >nul
  ) else if exist "config\default.json" (
    echo [INFO] Creating config\app.yaml from legacy default.json...
    copy /Y "config\default.json" "config\app.yaml" >nul
  )
)

echo [INFO] Starting subtitle app...
"%PYTHON%" src\main.py --config "config\app.yaml"
set EXIT_CODE=%ERRORLEVEL%
if not "%EXIT_CODE%"=="0" (
  echo [ERROR] Application exited with code %EXIT_CODE%.
  pause
)
exit /b %EXIT_CODE%
