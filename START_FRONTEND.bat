@echo off
cd /d "%~dp0frontend-app"
if not exist node_modules (
  echo Installing frontend dependencies...
  call npm install
  if errorlevel 1 pause & exit /b 1
)
call npm run dev
pause
