#!/usr/bin/env bash
set -euo pipefail
BASE=${ORCH_BASE:-http://127.0.0.1:8001}

echo "Running Provider Conformance Suite (local, offline) against $BASE"
curl -sS -X POST -H 'content-type: application/json' \
  "$BASE/providers/conformance/run" \
  -d '{"capabilities":["ads","lifecycle","experiments","cdp","vectorstore","llm_gateway"]}' | cat
echo


