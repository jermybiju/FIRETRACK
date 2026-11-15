#!/usr/bin/env bash
# FIRETRACK launcher (macOS / Linux)
#
#   ./run.sh              start on http://127.0.0.1:8000
#   PORT=9000 ./run.sh    start on another port
#
# First run creates .venv, installs FastAPI + uvicorn, and builds the hotspot
# database from the bundled NASA FIRMS snapshot.
set -euo pipefail

cd "$(dirname "$0")"
PORT="${PORT:-8000}"

echo ""
echo "  FIRETRACK  Unified Satellite Burning Activity Intelligence Platform"
echo "  ------------------------------------------------------------------"

PYTHON_BIN=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'; then
      PYTHON_BIN="$candidate"
      break
    fi
  fi
done
if [ -z "$PYTHON_BIN" ]; then
  echo "  Python 3.10+ was not found. Install it and try again." >&2
  exit 1
fi
echo "  Python: $PYTHON_BIN"

VENV_PY=".venv/bin/python"
if [ -x "$VENV_PY" ]; then
  echo "  Virtual environment: .venv"
elif [ -d ".pydeps/fastapi" ]; then
  echo "  Using bundled dependencies: .pydeps"
  VENV_PY="$PYTHON_BIN"
else
  echo "  Creating virtual environment (one time)..."
  "$PYTHON_BIN" -m venv .venv
  VENV_PY=".venv/bin/python"
fi

if ! "$VENV_PY" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  echo "  Installing FastAPI + uvicorn..."
  "$VENV_PY" -m pip install --disable-pip-version-check --quiet --upgrade pip
  "$VENV_PY" -m pip install --disable-pip-version-check --quiet -r requirements.txt
fi

export PYTHONPATH="$PWD/backend${PYTHONPATH:+:$PYTHONPATH}"
[ -d "$PWD/.pydeps" ] && export PYTHONPATH="$PWD/.pydeps:$PYTHONPATH"

if [ ! -f "frontend/dist/index.html" ]; then
  echo "  Note: frontend/dist is missing — the API runs, but the UI needs 'pnpm build' in frontend/." >&2
fi

echo "  Starting server on http://127.0.0.1:$PORT"
echo "  Press Ctrl+C to stop."
echo ""
exec "$VENV_PY" -X utf8 -m app.main --port "$PORT"
