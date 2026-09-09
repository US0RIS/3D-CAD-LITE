@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3.11 -V >nul 2>nul
  if errorlevel 1 (set PY=py -3) else (set PY=py -3.11)
) else (
  set PY=python
)
if not exist .venv (
  %PY% -m venv .venv
)
call .venv\Scripts\activate.bat
python -c "import cadquery,fastapi,scipy,uvicorn,multipart" >nul 2>nul
if errorlevel 1 pip install -r requirements.txt
start "" http://127.0.0.1:8765
python server.py
pause
