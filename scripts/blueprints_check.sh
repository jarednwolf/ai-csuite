#!/usr/bin/env bash
set -euo pipefail

# Env toggles
BLUEPRINTS_ENABLED=${BLUEPRINTS_ENABLED:-1}
BLUEPRINTS_OUTDIR=${BLUEPRINTS_OUTDIR:-blueprints}
BLUEPRINTS_ALLOW_WARN_OVERRIDE=${BLUEPRINTS_ALLOW_WARN_OVERRIDE:-0}

if [[ "$BLUEPRINTS_ENABLED" == "0" ]]; then
  echo "[blueprints] disabled via BLUEPRINTS_ENABLED=0" >&2
  exit 0
fi

PYTHON_BIN="python3"
if [[ -x ".venv/bin/python" ]]; then PYTHON_BIN=".venv/bin/python"; fi

$PYTHON_BIN scripts/blueprints_report.py

REPORT="${BLUEPRINTS_OUTDIR}/report.json"
if [[ ! -f "$REPORT" ]]; then
  echo "[blueprints] report not found at $REPORT" >&2
  exit 2
fi

# Basic gating based on summary.failed
CODE=0
FAILED=$($PYTHON_BIN - "$REPORT" <<'PY'
import json,sys
with open(sys.argv[1]) as f:
    rep=json.load(f)
print(int(rep.get('summary',{}).get('failed') or 0))
PY
)

if [[ "$FAILED" -gt 0 ]]; then
  echo "[blueprints] gating violations or manifest errors detected ($FAILED)" >&2
  CODE=1
fi

exit $CODE


