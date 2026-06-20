#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/root/projects/asb}"
UV_HOME="${APP_DIR}/.local/uv"
UV_PYTHON_DIR="${APP_DIR}/.local/python"
UV_BIN="${UV_HOME}/uv"

export PATH="${UV_HOME}:${PATH}"

if command -v python3.12 >/dev/null 2>&1; then
  echo "Python 3.12 already installed: $(python3.12 --version)"
  exit 0
fi

cd "$APP_DIR"

if [[ ! -x "$UV_BIN" ]]; then
  echo "==> Install uv"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$UV_HOME" UV_NO_MODIFY_PATH=1 sh
fi

echo "==> Install Python 3.12 via uv"
UV_PYTHON_INSTALL_DIR="$UV_PYTHON_DIR" "$UV_BIN" python install 3.12

PYTHON312="$(UV_PYTHON_INSTALL_DIR="$UV_PYTHON_DIR" "$UV_BIN" python find 3.12)"
ln -sf "$PYTHON312" /usr/local/bin/python3.12

python3.12 --version
