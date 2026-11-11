@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY if exist "C:\python314\python.exe" set "PY=C:\python314\python.exe"
if not defined PY set "PY=python"
%PY% -c "import PyQt6, OpenGL, certifi" >nul 2>&1 || (
  echo Installing requirements: PyQt6, PyOpenGL, certifi ...
  %PY% -m pip install -r requirements.txt
)
%PY% run.py
if errorlevel 1 pause
