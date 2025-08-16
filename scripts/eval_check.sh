#!/usr/bin/env bash
set -euo pipefail

# Env toggles
EVAL_ENABLED=${EVAL_ENABLED:-1}
EVAL_OUTDIR=${EVAL_OUTDIR:-eval}
EVAL_THRESHOLD=${EVAL_THRESHOLD:-0.9}
EVAL_ALLOW_WARN_OVERRIDE=${EVAL_ALLOW_WARN_OVERRIDE:-0}

if [[ "$EVAL_ENABLED" == "0" ]]; then
  echo "[eval] disabled via EVAL_ENABLED=0" >&2
  exit 0
fi

PYTHON_BIN="python3"
if [[ -x ".venv/bin/python" ]]; then PYTHON_BIN=".venv/bin/python"; fi

$PYTHON_BIN scripts/eval_run.py
$PYTHON_BIN scripts/eval_history.py

# Threshold gating: fail if any suite score < threshold
REPORT="${EVAL_OUTDIR}/report.json"
if [[ ! -f "$REPORT" ]]; then
  echo "[eval] report not found at $REPORT" >&2
  exit 2
fi

CODE=0
LOW=""
score_of() {
  # jq may not be available; use python for portability
  $PYTHON_BIN - "$1" "$2" <<'PY'
import json,sys
rep=json.load(open(sys.argv[1]))
thr=float(sys.argv[2])
bad=[s for s in rep.get('suites',[]) if float(s.get('score') or 0.0) < float(s.get('threshold') or thr)]
if bad:
  print("\n".join(sorted(str(b.get('id')) for b in bad)))
PY
}

LOW=$(score_of "$REPORT" "$EVAL_THRESHOLD" || true)
if [[ -n "$LOW" ]]; then
  echo "[eval] suites below threshold:"
  echo "$LOW"
  CODE=1
fi

exit $CODE


