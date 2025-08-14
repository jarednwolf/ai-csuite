# AI C‑Suite — Phase 1 (Bootstrap)

This Phase 1 scaffold brings up:
- FastAPI orchestrator (skeleton)
- Postgres (pgvector enabled)
- Redis (reserved for later)

## Prereqs
- Docker + Docker Compose

## Run locally
```bash
docker compose up --build


Then visit:

Health: http://localhost:8000/healthz

Docs: http://localhost:8000/docs

Create and inspect a run:

curl -X POST http://localhost:8000/runs \
  -H "content-type: application/json" \
  -d '{"tenant_id":"00000000-0000-0000-0000-000000000000","project_id":"11111111-1111-1111-1111-111111111111","roadmap_item_id":null,"phase":"delivery"}'

# Replace <RUN_ID>:
curl http://localhost:8000/runs/<RUN_ID>

Run tests locally (outside Docker)
python -m venv .venv && source .venv/bin/activate
pip install -r apps/orchestrator/requirements.txt
pip install pytest
PYTHONPATH=apps/orchestrator pytest -q
