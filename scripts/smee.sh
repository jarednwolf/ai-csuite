#!/usr/bin/env bash
set -euo pipefail

if ! command -v npx >/dev/null 2>&1; then
  echo "npx not found. Install Node (e.g., brew install node)." >&2
  exit 1
fi

SMEE_URL="${SMEE_URL:-}"
TARGET_URL="${TARGET_URL:-http://localhost:8000/webhooks/github}"

if [[ -z "$SMEE_URL" ]]; then
  echo "Set SMEE_URL (e.g., export SMEE_URL=https://smee.io/yourchannel) and rerun." >&2
  exit 1
fi

echo "Forwarding $SMEE_URL  ->  $TARGET_URL"
exec npx smee-client --url "$SMEE_URL" --target "$TARGET_URL"


