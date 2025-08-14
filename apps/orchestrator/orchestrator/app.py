
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uuid
import datetime as dt

app = FastAPI(title="AI C-suite Orchestrator (Phase 1)")

class RunCreate(BaseModel):
    tenant_id: str
    project_id: str
    roadmap_item_id: str | None = None
    phase: str = "delivery"

class Run(BaseModel):
    id: str
    status: str
    created_at: str

# Phase 1 uses in-memory storage (to be replaced by Postgres in Phase 2)
RUNS: dict[str, Run] = {}

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.post("/runs", response_model=Run)
def create_run(payload: RunCreate):
    run_id = str(uuid.uuid4())
    run = Run(id=run_id, status="pending", created_at=dt.datetime.utcnow().isoformat())
    RUNS[run_id] = run
    return run

@app.post("/runs/{run_id}/start")
def start_run(run_id: str):
    if run_id not in RUNS:
        raise HTTPException(404, "run not found")
    RUNS[run_id].status = "running"
    return {"run_id": run_id, "status": "started"}

@app.get("/runs/{run_id}", response_model=Run)
def get_run(run_id: str):
    if run_id not in RUNS:
        raise HTTPException(404, "run not found")
    return RUNS[run_id]

