#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="python3"
if [[ -x ".venv/bin/python" ]]; then PYTHON_BIN=".venv/bin/python"; fi

# Environment toggles (defaults)
IAC_ENABLED="${IAC_ENABLED:-1}"
IAC_ENV="${IAC_ENV:-staging}"
IAC_OUTDIR="${IAC_OUTDIR:-iac}"

RELEASE_ENABLED="${RELEASE_ENABLED:-1}"
RELEASE_ENV="${RELEASE_ENV:-$IAC_ENV}"
RELEASE_FIXTURES="${RELEASE_FIXTURES:-deployments/fixtures/canary_ok.json}"
ROLL_OUT_STEPS="${ROLL_OUT_STEPS:-10,50,100}"
ROLL_OUT_THRESH_ERR="${ROLL_OUT_THRESH_ERR:-0.02}"
ROLL_OUT_THRESH_P95="${ROLL_OUT_THRESH_P95:-800}"

export IAC_ENABLED IAC_ENV IAC_OUTDIR
export RELEASE_ENABLED RELEASE_ENV RELEASE_FIXTURES ROLL_OUT_STEPS ROLL_OUT_THRESH_ERR ROLL_OUT_THRESH_P95

if [[ "$IAC_ENABLED" != "0" ]]; then
  $PYTHON_BIN scripts/iac_plan.py
  $PYTHON_BIN scripts/iac_apply.py
fi

set +e
$PYTHON_BIN scripts/release_run.py
RC=$?
set -e

# Always write history, even on failure, for observability
$PYTHON_BIN scripts/release_history.py

exit $RC
