#!/usr/bin/env bash
set -euo pipefail
export ORCH_BASE=${ORCH_BASE:-http://127.0.0.1:8001}

PYTEST_BIN="pytest"
UVICORN_BIN="uvicorn"
if [[ -x ".venv/bin/pytest" ]]; then PYTEST_BIN=".venv/bin/pytest"; fi
if [[ -x ".venv/bin/uvicorn" ]]; then UVICORN_BIN=".venv/bin/uvicorn"; fi

# Stop any existing server to ensure deterministic environment
if pgrep -f "orchestrator.app:app" >/dev/null 2>&1; then
  pkill -f "orchestrator.app:app" || true
  sleep 1
fi

# Ensure deterministic state for local run (optional override with KEEP_DB=1)
if [[ "${KEEP_DB:-}" != "1" ]]; then rm -f dev.db || true; fi

# Start local app
$UVICORN_BIN --app-dir apps/orchestrator orchestrator.app:app --host 127.0.0.1 --port 8001 --log-level warning &
APP_PID=$!
sleep 1

$PYTEST_BIN -q apps/orchestrator/tests/test_run_start_auto_ensure.py \
            apps/orchestrator/tests/test_phase9_summary_md.py \
            apps/orchestrator/tests/test_phase9_webhook_sim.py \
            apps/orchestrator/tests/test_phase10_graph_happy_path.py \
            apps/orchestrator/tests/test_phase10_graph_backtrack.py \
            apps/orchestrator/tests/test_phase11_graph_happy_path.py \
            apps/orchestrator/tests/test_phase11_resume.py \
            apps/orchestrator/tests/test_phase11_retry_exhaust.py \
            apps/orchestrator/tests/test_phase12_personas.py \
            apps/orchestrator/tests/test_phase13_kb_files.py \
            apps/orchestrator/tests/test_phase14_observability.py \
            apps/orchestrator/tests/test_phase15_security.py \
            apps/orchestrator/tests/test_phase16_ui.py \
            apps/orchestrator/tests/test_phase17_blueprints_registry.py \
            apps/orchestrator/tests/test_phase17_scaffolder.py \
            apps/orchestrator/tests/test_phase18_preview_smoke.py \
            apps/orchestrator/tests/test_phase19_budget_aggregation.py \
            apps/orchestrator/tests/test_phase19_budget_status.py \
            apps/orchestrator/tests/test_phase21_supply_chain.py \
            apps/orchestrator/tests/test_phase22_policy_gates.py \
            apps/orchestrator/tests/test_phase23_redaction_audit.py \
            apps/orchestrator/tests/test_phase24_eval_harness.py \
            apps/orchestrator/tests/test_phase25_iac_release.py \
            apps/orchestrator/tests/test_phase26_blueprint_manifests.py \
            apps/orchestrator/tests/test_phase27_cockpit_blueprint_ui.py \
            apps/orchestrator/tests/test_phase28_scheduler_quotas.py \
            apps/orchestrator/tests/test_phase29_integrations.py

# Teardown
if [[ -n "${APP_PID:-}" ]]; then kill "$APP_PID" >/dev/null 2>&1 || true; fi


