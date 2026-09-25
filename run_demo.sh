#!/usr/bin/env bash
# RAQIB one-command demo (Git Bash on Windows, macOS, Linux)
set -euo pipefail
cd "$(dirname "$0")"
echo "=== RAQIB - one-command demo ==="

pybin() { if [ -x .venv/Scripts/python.exe ]; then echo .venv/Scripts/python; else echo .venv/bin/python; fi; }

if [ ! -x .venv/Scripts/python.exe ] && [ ! -x .venv/bin/python ]; then
  echo "[1/4] Creating the Python environment..."
  if command -v py >/dev/null 2>&1; then py -3.12 -m venv .venv || py -3.11 -m venv .venv || py -m venv .venv
  else python3 -m venv .venv; fi
  PY=$(pybin)
  "$PY" -m pip install --upgrade pip -q
  "$PY" -m pip install -r requirements.txt -q
  "$PY" -m pip install -e . -q
else
  echo "[1/4] Python environment found."
fi
PY=$(pybin)

if [ ! -f artifacts/metrics.json ]; then
  echo "[2/4] Building data, models and measured results (about 20 s)..."
  "$PY" -m raqib.build
else
  echo "[2/4] Artifacts found - build skipped (delete artifacts/metrics.json to rebuild)."
fi

if [ ! -f frontend/dist/index.html ]; then
  echo "[3/4] Building the web app..."
  ( cd frontend && { corepack pnpm install --frozen-lockfile && corepack pnpm build; } || { npm install && npm run build; } )
else
  echo "[3/4] Web app already built."
fi

echo "[4/4] Starting RAQIB at http://127.0.0.1:8000 (Ctrl+C to stop)"
exec "$PY" -m raqib.serve --port 8000 --open
