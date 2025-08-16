#!/usr/bin/env bash
set -euo pipefail

# Example CI hook: compute budgets and publish status/summary (dry-run friendly)
export ORCH_BASE=${ORCH_BASE:-http://localhost:8000}
RUN_ID="$1"
if [[ -z "${RUN_ID}" ]]; then
  echo "usage: $0 <run_id>" >&2
  exit 1
fi

curl -s -X POST "${ORCH_BASE}/integrations/budget/${RUN_ID}/compute" \
  -H 'content-type: application/json' \
  -d '{"warn_pct":0.8,"block_pct":1.0,"rate":{"usd_per_1k_tokens":0.01}}' | jq .

#!/usr/bin/env bash
set -euo pipefail

BASE=${ORCH_BASE:-http://localhost:8000}
OWNER=${E2E_REPO_OWNER:-acme}
REPO=${E2E_REPO_NAME:-demo}
BRANCH=${BRANCH_NAME:-feature/ci-preview}

export GITHUB_WRITE_ENABLED=${GITHUB_WRITE_ENABLED:-0}
export GITHUB_PR_ENABLED=${GITHUB_PR_ENABLED:-0}
export PREVIEW_ENABLED=${PREVIEW_ENABLED:-1}
export PREVIEW_BASE_URL=${PREVIEW_BASE_URL:-http://preview.local}

RUN_ID=${RUN_ID:-$(uuidgen)}
echo "RUN_ID=$RUN_ID"

echo "Deploying preview (dry-run=${GITHUB_WRITE_ENABLED})..."
curl -s -X POST "$BASE/integrations/preview/$RUN_ID/deploy" \
  -H 'content-type: application/json' \
  -d '{"owner":"'"$OWNER"'","repo":"'"$REPO"'","branch":"'"$BRANCH"'"}' | jq .

echo "Running smoke check..."
curl -s -X POST "$BASE/integrations/preview/$RUN_ID/smoke" \
  -H 'content-type: application/json' \
  -d '{"timeout_ms": 1000}' | jq .

echo "Fetching current preview info..."
curl -s "$BASE/integrations/preview/$RUN_ID" | jq .


