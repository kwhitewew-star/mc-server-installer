#!/usr/bin/env bash
# Start MC Server Installer on Linux / macOS.
cd "$(dirname "$0")" || exit 1
PY=${PYTHON:-python3}
if ! "$PY" -c "import PyQt6, OpenGL, certifi" >/dev/null 2>&1; then
  echo "Installing requirements: PyQt6, PyOpenGL, certifi ..."
  "$PY" -m pip install --user -r requirements.txt || exit 1
fi
exec "$PY" run.py "$@"
