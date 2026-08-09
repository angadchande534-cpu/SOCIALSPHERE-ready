@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo   SocialSphere - Installing dependencies
echo ==============================================

where py >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=py"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python was not found.
    echo Install Python and select "Add python.exe to PATH".
    pause
    exit /b 1
  )
  set "PYTHON_CMD=python"
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 goto :failed
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo Installation completed successfully.
echo Double-click start.bat to run SocialSphere.
pause
exit /b 0

:failed
echo.
echo Installation failed. Read the error shown above.
pause
exit /b 1
