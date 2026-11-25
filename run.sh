#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "====================================================================="
echo "      OPENSHORTS STUDIO - AI HIGHLIGHTS AND VIRAL AUTO-CLIPPER"
echo "====================================================================="
echo

# 1. Locate Python 3.10+
PY_CMD=""
for candidate in python3 python python3.12 python3.11 python3.10; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
      PY_CMD="$candidate"
      break
    fi
  fi
done

if [ -z "$PY_CMD" ]; then
  echo "[ERROR] Python 3.10 or higher is required."
  if [ "$(uname -s)" = "Darwin" ]; then
    echo "        Install with: brew install python@3.12"
  else
    echo "        Install with: sudo apt install python3 python3-venv python3-pip"
  fi
  exit 1
fi

# 2. Setup / Activate Virtual Environment
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "[*] Creating isolated Python environment in .venv..."
  "$PY_CMD" -m venv "$VENV_DIR"
fi
ACTIVE_PY="$VENV_DIR/bin/python"

# 3. Verify / Install Dependencies
if ! "$ACTIVE_PY" -c "import fastapi, uvicorn, pydantic, PIL, aiofiles, yt_dlp" >/dev/null 2>&1; then
  echo "[*] Installing required Python packages from requirements.txt..."
  "$ACTIVE_PY" -m pip install --upgrade pip --quiet || true
  "$ACTIVE_PY" -m pip install -r "$SCRIPT_DIR/requirements.txt"
fi

# 4. Run Zero-Touch Setup & Pre-Flight Hardware Diagnostics
"$ACTIVE_PY" "$SCRIPT_DIR/backend/bootstrap.py" --setup || true

# 5. Parse --lan flag
IS_LAN=0
for arg in "$@"; do
  if [ "$arg" = "--lan" ]; then
    IS_LAN=1
  fi
done

if [ "$IS_LAN" = "1" ]; then
  export OPENSHORTS_LAN=1
  HOST_BIND="0.0.0.0"
else
  export OPENSHORTS_LAN=0
  HOST_BIND="127.0.0.1"
fi

echo
echo "====================================================================="
echo "                    SERVER ACCESS URLS"
echo "====================================================================="
echo "  [Local PC]    http://localhost:8000"
echo "  [Local PC]    http://127.0.0.1:8000"
if [ "$IS_LAN" = "1" ]; then
  echo "  [LAN Mode]    Enabled on 0.0.0.0:8000"
else
  echo "  Tip: Run \"./run.sh --lan\" for Wi-Fi / mobile LAN access"
fi
echo "====================================================================="
echo

# 6. Open Browser
if [ "$(uname -s)" = "Darwin" ]; then
  open "http://localhost:8000" >/dev/null 2>&1 || true
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://localhost:8000" >/dev/null 2>&1 || true
fi

# 7. Start Uvicorn Server
exec "$ACTIVE_PY" -m uvicorn backend.main:app --host "$HOST_BIND" --port 8000
