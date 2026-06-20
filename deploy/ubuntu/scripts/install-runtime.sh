#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/root/projects/asb}"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
UV_HOME="${APP_DIR}/.local/uv"
UV_BIN="${UV_HOME}/uv"

export PATH="${UV_HOME}:${PATH}"

cd "$APP_DIR"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  bash deploy/ubuntu/scripts/install-python.sh
fi

if [[ ! -x "$UV_BIN" ]]; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$UV_HOME" UV_NO_MODIFY_PATH=1 sh
fi

"$PYTHON_BIN" -m venv .venv
"$UV_BIN" pip install -r requirements.txt --python .venv/bin/python

echo "Runtime ready: $(.venv/bin/python --version)"
