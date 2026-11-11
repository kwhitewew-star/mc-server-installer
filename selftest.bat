@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY if exist "C:\python314\python.exe" set "PY=C:\python314\python.exe"
if not defined PY set "PY=python"
%PY% -c "import certifi" >nul 2>&1 || %PY% -m pip install certifi
%PY% scripts\selftest.py
