@echo off
if "%~1"=="" (echo Usage: install.bat C:\path\to\Jarvis-for-MRB & exit /b 2)
python "%~dp0install.py" --jarvis "%~1"
