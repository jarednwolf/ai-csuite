#!/usr/bin/env bash
set -euo pipefail

echo "AI-CSuite Dev Doctor"
echo "---------------------"
command -v docker >/dev/null || { echo "Docker not found"; exit 1; }
command -v curl >/dev/null || { echo "curl not found"; exit 1; }

CTX=$(docker context show 2>/dev/null || echo "unknown")
echo "Docker context: $CTX"

if ! docker info >/dev/null 2>&1; then
  echo "❌ Docker engine not reachable. Start Docker Desktop."
  exit 1
fi
echo "✅ Docker engine reachable"

# Compose services
if ! docker compose ps >/dev/null 2>&1; then
  echo "ℹ️  Not in a compose project dir or compose not running."
else
  docker compose ps
fi

# API health
if curl -s http://localhost:8000/healthz | grep -q '"ok":'; then
  echo "✅ API /healthz OK"
else
  echo "❌ API not responding on http://localhost:8000/healthz"
fi

# DB tables
if docker compose ps postgres >/dev/null 2>&1; then
  echo "Checking DB tables..."
  docker compose exec -T postgres psql -U csuite -d csuite -c '\\dt' || true
fi

# .env checks
if [[ -f .env ]]; then
  GHTOKEN=$(grep -E '^GITHUB_TOKEN=' .env | cut -d= -f2- || true)
  if [[ -n "${GHTOKEN:-}" ]]; then
    echo "✅ GITHUB_TOKEN present (masked): ${GHTOKEN:0:6}******"
  else
    echo "ℹ️  GITHUB_TOKEN not set in .env (PR creation will be skipped)"
  fi
else
  echo "ℹ️  .env file not found"
fi

# Optional: verify repo access if --repo passed
REPO_URL=""
PROJECT_ID=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO_URL="$2"; shift 2 ;;
    --project-id) PROJECT_ID="$2"; shift 2 ;;
    *) shift ;;
  esac
done

if [[ -n "$REPO_URL" ]]; then
  echo "Verifying GitHub access for $REPO_URL ..."
  curl -s -X POST http://localhost:8000/integrations/github/verify \
    -H "content-type: application/json" \
    -d "{\"repo_url\":\"$REPO_URL\"}" | jq .
elif [[ -n "$PROJECT_ID" ]]; then
  echo "Verifying GitHub access for project $PROJECT_ID ..."
  curl -s -X POST http://localhost:8000/integrations/github/verify \
    -H "content-type: application/json" \
    -d "{\"project_id\":\"$PROJECT_ID\"}" | jq .
fi

echo "Dev Doctor complete."


