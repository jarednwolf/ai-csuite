#!/usr/bin/env bash
set -euo pipefail

echo "=== AI-CSuite Python 3.12.5 Environment Rebuild ==="

# Check for pyenv
if ! command -v pyenv &>/dev/null; then
  echo "❌ pyenv not found. Install with:"
  echo "brew install pyenv"
  exit 1
fi

# Ensure correct Python version is installed
if ! pyenv versions --bare | grep -qx "3.12.5"; then
  echo "📥 Installing Python 3.12.5..."
  pyenv install 3.12.5
else
  echo "✅ Python 3.12.5 already installed."
fi

# Set local version
echo "📌 Setting local Python version to 3.12.5..."
pyenv local 3.12.5

# Deactivate any active venv (best-effort; 'deactivate' may not be defined in a subshell)
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
  echo "🔌 Deactivating current venv (if possible)..."
  if command -v deactivate >/dev/null 2>&1; then
    deactivate || true
  else
    echo "ℹ️  'deactivate' not available in this shell; continuing."
  fi
fi

# Remove old venv
if [[ -d ".venv" ]]; then
  echo "🗑 Removing old .venv..."
  rm -rf .venv
fi

# Create new venv with pyenv’s Python 3.12.5
echo "📦 Creating new .venv with Python 3.12.5..."
# Resolve the correct python binary explicitly via pyenv (fallback to python3)
PY_BIN=""
if PY_BIN=$(pyenv which python 2>/dev/null); then
  :
fi
if [[ -z "${PY_BIN:-}" || ! -x "$PY_BIN" ]]; then
  echo "⚠️  Could not resolve pyenv python; trying python3 on PATH..."
  PY_BIN=$(command -v python3 || true)
fi
if [[ -z "${PY_BIN:-}" ]]; then
  echo "❌ No suitable Python interpreter found. Ensure pyenv is initialized or python3 is installed."
  exit 1
fi
"$PY_BIN" -m venv .venv

# Activate venv
echo "🔌 Activating new venv..."
source .venv/bin/activate || true

# Upgrade pip
echo "⬆️  Upgrading pip..."
.venv/bin/python -m pip install --upgrade pip

# Install requirements
echo "📥 Installing core requirements..."
.venv/bin/python -m pip install --no-cache-dir -r apps/orchestrator/requirements.txt

echo "📥 Installing dev requirements..."
.venv/bin/python -m pip install --no-cache-dir -r requirements-dev.txt || true

# Verify Python version
PYVER=$( .venv/bin/python --version 2>&1 )
if [[ "$PYVER" != "Python 3.12.5"* ]]; then
  echo "❌ Wrong Python version detected: $PYVER"
  exit 1
fi

echo "✅ Python version: $PYVER"
echo "✅ Environment ready. Run:"
echo "source .venv/bin/activate"
