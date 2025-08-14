#!/usr/bin/env bash
set -euo pipefail
export ORCH_BASE=${ORCH_BASE:-http://localhost:8000}
pytest -q apps/orchestrator/tests/test_run_start_auto_ensure.py \
          apps/orchestrator/tests/test_phase9_summary_md.py \
          apps/orchestrator/tests/test_phase9_webhook_sim.py


