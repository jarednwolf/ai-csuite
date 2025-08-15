#!/usr/bin/env bash
set -euo pipefail

REQ_PYTHON="3.12.5"
VENV_DIR=".venv"

echo "=== AI-CSuite Dev Environment Check & Sync ==="

# 1. Check local Python version
PY_VER=$(python3 --version | awk '{print $2}')
if [[ "$PY_VER" != "$REQ_PYTHON" ]]; then
  echo "❌ Python $REQ_PYTHON required, found $PY_VER"
  echo "Run: pyenv install $REQ_PYTHON && pyenv local $REQ_PYTHON"
  exit 1
else
  echo "✅ Python version OK ($PY_VER)"
fi

# 2. Ensure .python-version for pyenv
if [[ ! -f ".python-version" ]] || ! grep -q "$REQ_PYTHON" .python-version; then
  echo "$REQ_PYTHON" > .python-version
  echo "📄 Wrote .python-version"
fi

# 3. Patch Dockerfile(s) to match Python version
if grep -q "FROM python" Dockerfile; then
  sed -i.bak -E "s|FROM python:[0-9]+\.[0-9]+(\.[0-9]+)?|FROM python:${REQ_PYTHON}|g" Dockerfile
  echo "🐳 Dockerfile base image set to python:${REQ_PYTHON}"
fi

# 4. Patch GitHub Actions workflows
for wf in .github/workflows/*.yml; do
  if [[ -f "$wf" ]]; then
    sed -i.bak -E "s|python-version: ['\"]?[0-9]+\.[0-9]+(\.[0-9]+)?['\"]?|python-version: '${REQ_PYTHON}'|g" "$wf"
    echo "⚙️  Updated $wf to python-version ${REQ_PYTHON}"
  fi
done

# 5. Create venv if missing
if [[ ! -d "$VENV_DIR" ]]; then
  echo "📦 Creating virtualenv..."
  python3 -m venv "$VENV_DIR"
fi

# 6. Activate venv
source "$VENV_DIR/bin/activate"

# 7. Upgrade pip
pip install --upgrade pip

# 8. Install runtime deps
if [[ -f "apps/orchestrator/requirements.txt" ]]; then
  pip install --no-cache-dir -r apps/orchestrator/requirements.txt
else
  echo "⚠️ Missing apps/orchestrator/requirements.txt"
fi

# 9. Install dev deps
if [[ -f "requirements-dev.txt" ]]; then
  pip install --no-cache-dir -r requirements-dev.txt
fi

# 10. Verify numpy import
python -c "import numpy; print('✅ numpy import OK', numpy.__version__)" || {
  echo "❌ numpy failed to import"
  exit 1
}

# 11. Run tests
if command -v pytest >/dev/null; then
  echo "🧪 Running tests..."
  pytest -q || {
    echo "❌ Tests failed"
    exit 1
  }
else
  echo "⚠️ pytest not installed"
fi

echo "=== Environment & Workflow Sync Complete ==="
