#!/usr/bin/env bash
set -euo pipefail
export ORCH_BASE=${ORCH_BASE:-http://127.0.0.1:8001}

PYTEST_BIN="pytest"
UVICORN_BIN="uvicorn"
PYTHON_BIN="python3"
if [[ -x ".venv/bin/pytest" ]]; then PYTEST_BIN=".venv/bin/pytest"; fi
if [[ -x ".venv/bin/uvicorn" ]]; then UVICORN_BIN=".venv/bin/uvicorn"; fi
if [[ -x ".venv/bin/python" ]]; then PYTHON_BIN=".venv/bin/python"; fi

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

# Wait for healthz (deterministic startup)
$PYTHON_BIN - <<'PY'
import os, sys, time, urllib.request
base=os.getenv('ORCH_BASE','http://127.0.0.1:8001')
deadline=time.time()+10
ok=False
while time.time()<deadline:
    try:
        with urllib.request.urlopen(f"{base}/healthz", timeout=1.0) as r:
            if r.status==200:
                ok=True
                break
    except Exception:
        pass
    time.sleep(0.25)
sys.exit(0 if ok else 1)
PY


$PYTEST_BIN -q "$@" apps/orchestrator/tests/test_run_start_auto_ensure.py \
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
            apps/orchestrator/tests/test_phase54_adapter_scaffold.py \
            apps/orchestrator/tests/test_phase55_deps_supplychain.py \
            apps/orchestrator/tests/test_phase56_blueprint_autogen.py \
            apps/orchestrator/tests/test_phase25_iac_release.py \
            apps/orchestrator/tests/test_phase26_blueprint_manifests.py \
            apps/orchestrator/tests/test_phase27_cockpit_blueprint_ui.py \
            apps/orchestrator/tests/test_phase28_scheduler_quotas.py \
            apps/orchestrator/tests/test_phase29_integrations.py \
            apps/orchestrator/tests/test_phase31_pal_conformance.py \
            apps/orchestrator/tests/test_phase32_shadow_switch.py \
            apps/orchestrator/tests/test_phase33_llm_gateway_routing.py \
            apps/orchestrator/tests/test_phase34_cdp_contracts.py \
            apps/orchestrator/tests/test_phase35_experiments_bandits.py \
            apps/orchestrator/tests/test_phase36_bi_insights_suggestions.py \
            apps/orchestrator/tests/test_phase37_lifecycle_compliance.py \
            apps/orchestrator/tests/test_phase38_ads_guardrails.py \
            apps/orchestrator/tests/test_phase39_attribution_reverse_etl.py \
            apps/orchestrator/tests/test_phase40_evals_gates.py \
            apps/orchestrator/tests/test_phase41_vectorstore_swap.py \
            apps/orchestrator/tests/test_phase42_content_policy.py \
            apps/orchestrator/tests/test_phase43_roi_planning.py \
            apps/orchestrator/tests/test_phase44_billing.py \
            apps/orchestrator/tests/test_phase45_enterprise.py \
            apps/orchestrator/tests/test_phase46_cockpit_growth.py \
            apps/orchestrator/tests/test_phase47_repo_map.py \
            apps/orchestrator/tests/test_phase48_contract_coverage.py \
            apps/orchestrator/tests/test_phase49_self_docs_pr.py \
            apps/orchestrator/tests/test_phase50_test_synthesis.py \
            apps/orchestrator/tests/test_phase51_speculative_exec.py \
            apps/orchestrator/tests/test_phase52_agent_review_adr.py \
            apps/orchestrator/tests/test_phase53_lowrisk_automerge.py \
            apps/orchestrator/tests/test_phase57_self_canary.py \
            apps/orchestrator/tests/test_phase58_self_eval_gates.py \
            apps/orchestrator/tests/test_phase59_cost_perf_optimizer.py \
            apps/orchestrator/tests/test_phase60_self_healing.py \
            apps/orchestrator/tests/test_phase61_vendor_swap.py

# Teardown
if [[ -n "${APP_PID:-}" ]]; then kill "$APP_PID" >/dev/null 2>&1 || true; fi


