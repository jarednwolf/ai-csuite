#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
PYTHON_BIN="python3"
if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then PYTHON_BIN="$REPO_ROOT/.venv/bin/python"; fi

# Toggle
if [[ "${POLICY_ENABLED:-1}" == "0" ]]; then
  echo "Policies disabled via POLICY_ENABLED=0" >&2
  exit 0
fi

# Ensure output dir
mkdir -p "$REPO_ROOT/policy"

# Normalize facts (accept fixture via env POLICY_INPUT)
FACTS_ARG=()
if [[ -n "${POLICY_INPUT:-}" ]]; then
  FACTS_ARG=("--facts" "$POLICY_INPUT")
fi

"$PYTHON_BIN" "$REPO_ROOT/scripts/policy_input_collect.py" ${FACTS_ARG[@]:-}

# Evaluate policies (bundle path honored via POLICY_BUNDLE)
"$PYTHON_BIN" "$REPO_ROOT/scripts/policy_eval.py"

echo "Policy check completed (report at policy/report.json)"


