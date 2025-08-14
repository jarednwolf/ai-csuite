#!/usr/bin/env bash
set -euo pipefail
for i in {1..60}; do
  if curl -sf http://localhost:8000/healthz >/dev/null; then
    echo "API healthy"
    exit 0
  fi
  sleep 2
done
echo "API failed to become healthy in time" >&2
exit 1


