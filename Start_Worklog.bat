@echo off
cd /d "%~dp0"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":8765 .*LISTENING"') do set "RUNNING_PID=%%P"
if defined RUNNING_PID (
  echo Worklog already has a server on port 8765 (PID %RUNNING_PID%). Opening it without starting a duplicate.
  start "" "http://127.0.0.1:8765/"
  exit /b 0
)
echo Starting Worklog Version 3 at http://127.0.0.1:8765/
echo Keep this window open while using the application.
start "" "http://127.0.0.1:8765/"
python -u server.py
if errorlevel 1 pause
