#!/usr/bin/env bash
set -euo pipefail
export ORCH_BASE=${ORCH_BASE:-http://localhost:8000}

# Prefer venv pytest if available
PYTEST_BIN="pytest"
if [[ -x ".venv/bin/pytest" ]]; then
  PYTEST_BIN=".venv/bin/pytest"
fi

$PYTEST_BIN -q apps/orchestrator/tests/test_run_start_auto_ensure.py \
            apps/orchestrator/tests/test_phase9_summary_md.py \
            apps/orchestrator/tests/test_phase9_webhook_sim.py \
            apps/orchestrator/tests/test_phase10_graph_happy_path.py \
            apps/orchestrator/tests/test_phase10_graph_backtrack.py \
            apps/orchestrator/tests/test_phase11_graph_happy_path.py \
            apps/orchestrator/tests/test_phase11_resume.py \
            apps/orchestrator/tests/test_phase11_retry_exhaust.py \
            apps/orchestrator/tests/test_phase12_personas.py


