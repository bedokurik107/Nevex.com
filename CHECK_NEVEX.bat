@echo off
cd /d "%~dp0"
echo === NEVEX health ===
curl -s http://127.0.0.1:8000/health
echo.
echo === MRKT status ===
curl -s http://127.0.0.1:8000/api/mrkt/status
echo.
echo === gifts ===
curl -s http://127.0.0.1:8000/api/gifts?limit=5
echo.
echo === stats ===
curl -s http://127.0.0.1:8000/api/stats
echo.
pause
