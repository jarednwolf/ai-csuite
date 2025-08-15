#!/usr/bin/env bash
set -euo pipefail

# Wait for orchestrator container logs to show uvicorn running, then poll /healthz
deadline=$((SECONDS + 180))
echo "Waiting up to 180s for API to become healthy..."
while (( SECONDS < deadline )); do
  if curl -sf http://localhost:8000/healthz >/dev/null; then
    echo "API healthy"
    exit 0
  fi
  # Show a brief log tail to help debugging if failing
  docker compose logs --no-color --tail=20 orchestrator || true
  sleep 3
done
echo "API failed to become healthy in time" >&2
exit 1


