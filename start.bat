@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo   Starting SocialSphere on port 8000
echo ==============================================

if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment is missing. Running installer...
  call install.bat
  if errorlevel 1 exit /b 1
)

start "" http://127.0.0.1:8000
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

pause
