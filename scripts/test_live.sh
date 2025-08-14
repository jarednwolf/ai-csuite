#!/usr/bin/env bash
set -euo pipefail
: "${GITHUB_TOKEN:?Need GITHUB_TOKEN}"
: "${E2E_REPO_OWNER:?Need E2E_REPO_OWNER}"
: "${E2E_REPO_NAME:?Need E2E_REPO_NAME}"
export ORCH_BASE=${ORCH_BASE:-http://localhost:8000}

pytest -q apps/orchestrator/tests/test_phase7_statuses_merge.py \
          apps/orchestrator/tests/test_phase9_pr_comment.py


