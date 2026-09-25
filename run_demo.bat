@echo off
setlocal
cd /d "%~dp0"
echo === RAQIB - one-command demo ===

if not exist .venv\Scripts\python.exe (
  echo [1/4] Creating the Python environment...
  py -3.12 -m venv .venv 2>nul || py -3.11 -m venv .venv 2>nul || python -m venv .venv
  if not exist .venv\Scripts\python.exe goto :error
  .venv\Scripts\python -m pip install --upgrade pip -q
  .venv\Scripts\python -m pip install -r requirements.txt -q || goto :error
  .venv\Scripts\python -m pip install -e . -q || goto :error
) else (
  echo [1/4] Python environment found.
)

echo [2/4] Checking the built artifacts...
.venv\Scripts\python -m raqib.check
if errorlevel 1 (
  echo [2/4] Building data, models and measured results - about 20 s...
  .venv\Scripts\python -m raqib.build || goto :error
)

if not exist frontend\dist\index.html (
  echo [3/4] Building the web app...
  pushd frontend
  call corepack pnpm install --frozen-lockfile && call corepack pnpm build || (call npm install && call npm run build)
  popd
  if not exist frontend\dist\index.html goto :error
) else (
  echo [3/4] Web app already built.
)

echo [4/4] Starting RAQIB at http://127.0.0.1:8000  - press Ctrl+C to stop
.venv\Scripts\python -m raqib.serve --port 8000 --open
goto :eof

:error
echo.
echo Something failed - see the messages above.
pause
exit /b 1
