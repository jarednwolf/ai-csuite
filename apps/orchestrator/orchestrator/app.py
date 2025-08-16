
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
import uuid, datetime as dt
from typing import Optional, List, Dict
import os

from .db import Base, engine, get_db
from .models import RunDB, Project, RoadmapItem, PRD, DesignCheck, ResearchNote, KbChunk, PullRequest
from .schemas import (
    RunCreate, RunRead,
    ProjectCreate, ProjectRead, ProjectUpdate,  # NEW
    RoadmapItemCreate, RoadmapItemRead, RoadmapItemUpdate,
    PRDRead, DesignCheckRead, ResearchNoteRead, DiscoveryStatus,
    KbIngest, KbSearchResult, GithubVerify, PRRead,
    KbFileIngest,
)
from .graph import run_delivery_cycle, ensure_discovery_and_gate
from .discovery import dor_check, upsert_discovery_artifacts  # ensure import
from .kb import ingest_text as kb_ingest, search as kb_search
from .kb import ingest_document, markdown_to_text, pdf_to_text_bytes
from .integrations.github import verify_repo_access, open_pr_for_run
from .integrations.github import upsert_pr_summary_comment_for_run
from .webhooks import router as webhooks_router
from .api.blueprints_endpoints import router as blueprints_router
from .api.app_factory_endpoints import router as app_factory_router
from .api.preview_endpoints import router as preview_router
from .api.alerts_endpoints import router as alerts_router
from .api.budget_endpoints import router as budget_router
from .api.scheduler_endpoints import router as scheduler_router
from .api.partners_endpoints import router as partners_router
from .api.postmortem_endpoints import router as postmortem_router
from .blueprints.registry import registry as _bp_registry
from .integrations.github import ensure_and_update_for_branch_event
from .integrations.github import approve_pr_for_run, refresh_dor_status_for_run, statuses_for_run, merge_pr_for_run, set_status_for_run
from .security import audit_event

app = FastAPI(title="AI C-suite Orchestrator (Phase 17)")

# --- Startup: ensure tables exist (tolerant if DB not ready yet) ---
@app.on_event("startup")
def on_startup():
    # CI may start app before Postgres is ready. Try briefly, then defer to lazy init in get_db().
    for _ in range(30):
        try:
            Base.metadata.create_all(bind=engine)
            break
        except Exception:
            try:
                import time as _t
                _t.sleep(1)
            except Exception:
                break
    # Validate and cache blueprint manifests (fail fast on invalid)
    _bp_registry().load()

app.include_router(webhooks_router)
app.include_router(blueprints_router)
app.include_router(app_factory_router)
app.include_router(preview_router)
app.include_router(alerts_router)
app.include_router(budget_router)
app.include_router(scheduler_router)
app.include_router(partners_router)
app.include_router(postmortem_router)

# ---------- Health ----------
@app.get("/healthz")
def healthz():
    return {"ok": True}

# ---------- Runs ----------
@app.post("/runs", response_model=RunRead)
def create_run(payload: RunCreate, db: Session = Depends(get_db)):
    run_id = str(uuid.uuid4())
    now = dt.datetime.utcnow()
    db_obj = RunDB(
        id=run_id,
        tenant_id=payload.tenant_id,
        project_id=payload.project_id,
        roadmap_item_id=payload.roadmap_item_id,
        phase=payload.phase,
        status="pending",
        created_at=now,
    )
    db.add(db_obj)
    db.commit()
    return RunRead(id=run_id, status=db_obj.status, created_at=now)

@app.post("/runs/{run_id}/start")
def start_run(run_id: str, db: Session = Depends(get_db)):
    run = db.get(RunDB, run_id)
    if not run:
        raise HTTPException(404, "run not found")

    # 1) Auto-ensure discovery & DoR gate (never returns 'missing' just because artifacts didn't exist)
    ok, missing = ensure_discovery_and_gate(db, run)
    if not ok:
        run.status = "blocked"
        db.commit()
        return {"run_id": run_id, "status": "blocked", "missing": missing}

    # 2) Delivery cycle (agents, planning, implementation, etc.)
    run_delivery_cycle(db, run_id)

    # 3) Open (or update) PR — may be skipped gracefully
    pr_info = open_pr_for_run(db, run_id)
    resp = {"run_id": run_id, "status": "succeeded"}
    if isinstance(pr_info, dict):
        if "url" in pr_info:
            resp.update({"pr_url": pr_info["url"], "pr_number": pr_info.get("number"), "branch": pr_info.get("branch")})
        elif "skipped" in pr_info:
            resp["pr_skipped"] = pr_info["skipped"]
    return resp

@app.get("/runs/{run_id}", response_model=RunRead)
def get_run(run_id: str, db: Session = Depends(get_db)):
    db_obj = db.get(RunDB, run_id)
    if not db_obj:
        raise HTTPException(404, "run not found")
    return RunRead(id=db_obj.id, status=db_obj.status, created_at=db_obj.created_at)

@app.get("/runs/{run_id}/pr", response_model=PRRead)
def get_run_pr(run_id: str, db: Session = Depends(get_db)):
    row = (
        db.query(PullRequest)
        .filter(PullRequest.run_id == run_id)
        .order_by(PullRequest.created_at.desc())
        .first()
    )
    if not row:
        raise HTTPException(404, "no PR recorded for this run")
    return PRRead(
        id=row.id, run_id=row.run_id, project_id=row.project_id,
        repo=row.repo, branch=row.branch, number=row.number,
        url=row.url, state=row.state, created_at=row.created_at
    )

# ---------- Projects ----------
@app.post("/projects", response_model=ProjectRead)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    proj = Project(
        id=str(uuid.uuid4()),
        tenant_id=payload.tenant_id,
        name=payload.name,
        description=payload.description,
        repo_url=payload.repo_url,
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return ProjectRead(
        id=proj.id, tenant_id=proj.tenant_id, name=proj.name,
        description=proj.description, repo_url=proj.repo_url,
        created_at=proj.created_at,
    )

@app.get("/projects", response_model=List[ProjectRead])
def list_projects(tenant_id: Optional[str] = Query(default=None), db: Session = Depends(get_db)):
    q = db.query(Project)
    if tenant_id:
        q = q.filter(Project.tenant_id == tenant_id)
    items = q.order_by(Project.created_at.desc()).all()
    return [ProjectRead(
        id=p.id, tenant_id=p.tenant_id, name=p.name,
        description=p.description, repo_url=p.repo_url,
        created_at=p.created_at
    ) for p in items]

@app.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "project not found")
    return ProjectRead(
        id=p.id, tenant_id=p.tenant_id, name=p.name,
        description=p.description, repo_url=p.repo_url,
        created_at=p.created_at
    )

# NEW: project update
@app.patch("/projects/{project_id}", response_model=ProjectRead)
def update_project(project_id: str, patch: ProjectUpdate, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "project not found")
    if patch.name is not None: p.name = patch.name
    if patch.description is not None: p.description = patch.description
    if patch.repo_url is not None: p.repo_url = patch.repo_url
    db.commit()
    db.refresh(p)
    return ProjectRead(
        id=p.id, tenant_id=p.tenant_id, name=p.name,
        description=p.description, repo_url=p.repo_url, created_at=p.created_at
    )

# ---------- Roadmap Items ----------
@app.post("/roadmap-items", response_model=RoadmapItemRead)
def create_roadmap_item(payload: RoadmapItemCreate, db: Session = Depends(get_db)):
    if not db.get(Project, payload.project_id):
        raise HTTPException(400, "project_id not found")
    rm = RoadmapItem(
        id=str(uuid.uuid4()),
        tenant_id=payload.tenant_id,
        project_id=payload.project_id,
        title=payload.title,
        description=payload.description,
        status="planned",
        priority=payload.priority,
        target_release=payload.target_release,
    )
    db.add(rm)
    db.commit()
    db.refresh(rm)
    return RoadmapItemRead(
        id=rm.id, tenant_id=rm.tenant_id, project_id=rm.project_id,
        title=rm.title, description=rm.description, status=rm.status,
        priority=rm.priority, target_release=rm.target_release
    )

@app.get("/roadmap-items", response_model=List[RoadmapItemRead])
def list_roadmap_items(
    tenant_id: Optional[str] = Query(default=None),
    project_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(RoadmapItem)
    if tenant_id:
        q = q.filter(RoadmapItem.tenant_id == tenant_id)
    if project_id:
        q = q.filter(RoadmapItem.project_id == project_id)
    if status:
        q = q.filter(RoadmapItem.status == status)
    items = q.order_by(RoadmapItem.priority.asc()).all()
    return [RoadmapItemRead(
        id=i.id, tenant_id=i.tenant_id, project_id=i.project_id,
        title=i.title, description=i.description,
        status=i.status, priority=i.priority, target_release=i.target_release
    ) for i in items]

@app.get("/roadmap-items/{item_id}", response_model=RoadmapItemRead)
def get_roadmap_item(item_id: str, db: Session = Depends(get_db)):
    i = db.get(RoadmapItem, item_id)
    if not i:
        raise HTTPException(404, "roadmap item not found")
    return RoadmapItemRead(
        id=i.id, tenant_id=i.tenant_id, project_id=i.project_id,
        title=i.title, description=i.description,
        status=i.status, priority=i.priority, target_release=i.target_release
    )

@app.patch("/roadmap-items/{item_id}", response_model=RoadmapItemRead)
def update_roadmap_item(item_id: str, patch: RoadmapItemUpdate, db: Session = Depends(get_db)):
    i = db.get(RoadmapItem, item_id)
    if not i:
        raise HTTPException(404, "roadmap item not found")
    if patch.title is not None: i.title = patch.title
    if patch.description is not None: i.description = patch.description
    if patch.status is not None: i.status = patch.status
    if patch.priority is not None: i.priority = patch.priority
    db.commit()
    db.refresh(i)
    return RoadmapItemRead(
        id=i.id, tenant_id=i.tenant_id, project_id=i.project_id,
        title=i.title, description=i.description,
        status=i.status, priority=i.priority, target_release=i.target_release
    )

# ---------- KB (RAG) ----------
@app.post("/kb/ingest")
def kb_ingest_endpoint(payload: KbIngest, db: Session = Depends(get_db)):
    count = kb_ingest(
        db,
        tenant_id=payload.tenant_id,
        project_id=payload.project_id,
        kind=payload.kind,
        ref_id=payload.ref_id or "",
        text=payload.text,
    )
    return {"chunks": count}

@app.get("/kb/search", response_model=List[KbSearchResult])
def kb_search_endpoint(
    tenant_id: str = Query(...),
    project_id: str = Query(...),
    q: str = Query(...),
    k: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db)
):
    hits = kb_search(db, tenant_id=tenant_id, project_id=project_id, query=q, k=k)
    return [KbSearchResult(**h) for h in hits]

# --- Phase 13: File ingestion (markdown, pdf, text) ---
import base64
from typing import Literal

@app.post("/kb/ingest-file")
def kb_ingest_file_endpoint(payload: KbFileIngest, db: Session = Depends(get_db)):
    # Validate project exists
    proj = db.get(Project, payload.project_id)
    if not proj:
        raise HTTPException(400, "project_id not found")

    filename = payload.filename or ""
    content_type: Literal["markdown", "pdf", "text"] = payload.content_type  # type: ignore
    ref_id = payload.ref_id or filename

    # Decode/normalize to text
    text = ""
    if content_type == "markdown":
        src = payload.text
        if (not src) and payload.content_b64:
            try:
                src = base64.b64decode(payload.content_b64.encode("utf-8")).decode("utf-8", errors="ignore")
            except Exception:
                raise HTTPException(400, "invalid base64 for markdown text")
        if not src:
            raise HTTPException(400, "markdown text missing")
        text = markdown_to_text(src)
        kind = "file-md"
    elif content_type == "text":
        src = payload.text
        if (not src) and payload.content_b64:
            try:
                src = base64.b64decode(payload.content_b64.encode("utf-8")).decode("utf-8", errors="ignore")
            except Exception:
                raise HTTPException(400, "invalid base64 for text")
        if not src:
            raise HTTPException(400, "text missing")
        text = (src or "").strip()
        kind = "file-md"  # treat plain text as md-like for consistency
    elif content_type == "pdf":
        if not payload.content_b64:
            raise HTTPException(400, "pdf requires content_b64")
        try:
            pdf_bytes = base64.b64decode(payload.content_b64.encode("utf-8"))
        except Exception:
            raise HTTPException(400, "invalid base64 for pdf")
        text = pdf_to_text_bytes(pdf_bytes)
        if not text:
            raise HTTPException(400, "empty or invalid PDF (no extractable text)")
        kind = "file-pdf"
    else:
        raise HTTPException(400, "unsupported content_type")

    # Ingest
    count = ingest_document(db, tenant_id=payload.tenant_id, project_id=payload.project_id, kind=kind, ref_id=ref_id, text=text)
    return {"chunks": count, "kind": kind, "ref_id": ref_id, "filename": filename}

# ---------- Discovery status (with related) ----------
@app.get("/roadmap-items/{item_id}/discovery", response_model=DiscoveryStatus)
def discovery_status(item_id: str, db: Session = Depends(get_db)):
    item = db.get(RoadmapItem, item_id)
    if not item:
        raise HTTPException(404, "roadmap item not found")
    ok, missing, details = dor_check(db, item.tenant_id, item.project_id, item_id)

    prd = db.get(PRD, details.get("prd_id")) if "prd_id" in details else None
    design = db.get(DesignCheck, details.get("design_id")) if "design_id" in details else None
    research = db.get(ResearchNote, details.get("research_id")) if "research_id" in details else None

    related = kb_search(db, item.tenant_id, item.project_id, f"{item.title}", k=5)

    prd_read = PRDRead(
        id=prd.id, tenant_id=prd.tenant_id, project_id=prd.project_id,
        roadmap_item_id=prd.roadmap_item_id, version=prd.version,
        prd=prd.prd_json, created_at=prd.created_at
    ) if prd else None

    design_read = DesignCheckRead(
        id=design.id, tenant_id=design.tenant_id, project_id=design.project_id,
        roadmap_item_id=design.roadmap_item_id, passes=design.passes,
        heuristics_score=design.heuristics_score, a11y_notes=design.a11y_notes,
        created_at=design.created_at
    ) if design else None

    research_read = ResearchNoteRead(
        id=research.id, tenant_id=research.tenant_id, project_id=research.project_id,
        roadmap_item_id=research.roadmap_item_id, summary=research.summary,
        evidence=research.evidence, created_at=research.created_at
    ) if research else None

    return DiscoveryStatus(
        dor_pass=ok, missing=missing,
        prd=prd_read, design=design_read, research=research_read,
        related=[KbSearchResult(**r) for r in related]
    )

# NEW: discovery ensure endpoint (idempotent; may create artifacts)
@app.post("/roadmap-items/{item_id}/discovery/ensure", response_model=DiscoveryStatus)
def discovery_ensure(item_id: str, force: bool = Query(False), db: Session = Depends(get_db)):
    item = db.get(RoadmapItem, item_id)
    if not item:
        raise HTTPException(404, "roadmap item not found")

    # ensure artifacts exist (or refresh if force)
    upsert_discovery_artifacts(db, item.tenant_id, item.project_id, item_id, force=force)

    # recompute DoR and related
    ok, missing, details = dor_check(db, item.tenant_id, item.project_id, item_id)
    prd = db.get(PRD, details.get("prd_id")) if "prd_id" in details else None
    design = db.get(DesignCheck, details.get("design_id")) if "design_id" in details else None
    research = db.get(ResearchNote, details.get("research_id")) if "research_id" in details else None
    related = kb_search(db, item.tenant_id, item.project_id, f"{item.title}", k=5)

    prd_read = PRDRead(
        id=prd.id, tenant_id=prd.tenant_id, project_id=prd.project_id,
        roadmap_item_id=prd.roadmap_item_id, version=prd.version,
        prd=prd.prd_json, created_at=prd.created_at
    ) if prd else None

    design_read = DesignCheckRead(
        id=design.id, tenant_id=design.tenant_id, project_id=design.project_id,
        roadmap_item_id=design.roadmap_item_id, passes=design.passes,
        heuristics_score=design.heuristics_score, a11y_notes=design.a11y_notes,
        created_at=design.created_at
    ) if design else None

    research_read = ResearchNoteRead(
        id=research.id, tenant_id=research.tenant_id, project_id=research.project_id,
        roadmap_item_id=research.roadmap_item_id, summary=research.summary,
        evidence=research.evidence, created_at=research.created_at
    ) if research else None

    return DiscoveryStatus(
        dor_pass=ok, missing=missing,
        prd=prd_read, design=design_read, research=research_read,
        related=[KbSearchResult(**r) for r in related]
    )

# ---------- GitHub integration ----------
@app.post("/integrations/github/verify")
def github_verify(payload: GithubVerify, db: Session = Depends(get_db)):
    repo_url = payload.repo_url
    if payload.project_id and not repo_url:
        proj = db.get(Project, payload.project_id)
        if not proj:
            raise HTTPException(404, "project not found")
        repo_url = proj.repo_url
    if not repo_url:
        raise HTTPException(400, "repo_url missing (pass repo_url or project_id)")
    res = verify_repo_access(repo_url)
    if not res.get("ok"):
        raise HTTPException(400, res.get("reason", "verification failed"))
    return res

# --- Phase 8: manual ensure endpoint ---
from pydantic import BaseModel
from .ai_graph.graph import start_graph_run, get_graph_state, build_graph, set_graph_state
from .ai_graph.service import resume_from_last, compute_run_metrics
from .ai_graph.repo import get_history as repo_get_history, get_last as repo_get_last

class EnsurePRBody(BaseModel):
    owner: str
    repo: str
    branch: str
    number: int | None = None

@app.post("/integrations/github/pr/ensure-artifacts")
def ensure_pr_artifacts(body: EnsurePRBody, db: Session = Depends(get_db)):
    res = ensure_and_update_for_branch_event(db, body.owner, body.repo, body.branch, body.number)
    if "error" in res:
        raise HTTPException(400, res["error"])
    return res

# ---------- GitHub PR statuses & merge policy ----------

@app.get("/integrations/github/pr/{run_id}/statuses")
def github_pr_statuses(run_id: str, db: Session = Depends(get_db)):
    res = statuses_for_run(db, run_id)
    if "error" in res or "skipped" in res:
        raise HTTPException(400, res.get("error") or res.get("skipped"))
    return res

@app.post("/integrations/github/pr/{run_id}/approve")
def github_pr_approve(run_id: str, db: Session = Depends(get_db)):
    res = approve_pr_for_run(db, run_id)
    if "error" in res or "skipped" in res:
        raise HTTPException(400, res.get("error") or res.get("skipped"))
    try:
        audit_event(db, actor="api", event_type="github.approve", run_id=run_id, request_id=f"{run_id}:gh:approve", details={"result": res})
    except Exception:
        pass
    # return updated status summary
    return statuses_for_run(db, run_id)

@app.post("/integrations/github/pr/{run_id}/refresh-status")
def github_pr_refresh(run_id: str, db: Session = Depends(get_db)):
    # Re-evaluate DoR and update status; return updated statuses
    res = refresh_dor_status_for_run(db, run_id)
    if "error" in res or "skipped" in res:
        raise HTTPException(400, res.get("error") or res.get("skipped"))
    try:
        audit_event(db, actor="api", event_type="github.refresh_dor", run_id=run_id, request_id=f"{run_id}:gh:refresh", details={"result": res})
    except Exception:
        pass
    return statuses_for_run(db, run_id)

@app.post("/integrations/github/pr/{run_id}/merge")
def github_pr_merge(run_id: str, method: str = Query("squash"), db: Session = Depends(get_db)):
    res = merge_pr_for_run(db, run_id, method=method)
    if res.get("blocked"):
        raise HTTPException(400, f"merge blocked: {res.get('reason')}")
    if "error" in res or "skipped" in res:
        raise HTTPException(400, res.get("error") or res.get("skipped"))
    try:
        audit_event(db, actor="api", event_type="github.merge", run_id=run_id, request_id=f"{run_id}:gh:merge", details={"method": method, "result": res})
    except Exception:
        pass
    return res

@app.post("/integrations/github/pr/{run_id}/comment/refresh")
def github_pr_comment_refresh(run_id: str, db: Session = Depends(get_db)):
    res = upsert_pr_summary_comment_for_run(db, run_id)
    if "error" in res or "skipped" in res:
        raise HTTPException(400, res.get("error") or res.get("skipped"))
    return res

@app.patch("/roadmap-items/{item_id}", response_model=RoadmapItemRead)
def update_roadmap_item(item_id: str, patch: RoadmapItemUpdate, db: Session = Depends(get_db)):
    i = db.get(RoadmapItem, item_id)
    if not i:
        raise HTTPException(404, "roadmap item not found")
    if patch.title is not None: i.title = patch.title
    if patch.description is not None: i.description = patch.description
    if patch.status is not None: i.status = patch.status
    if patch.priority is not None: i.priority = patch.priority
    db.commit()
    db.refresh(i)
    return RoadmapItemRead(
        id=i.id, tenant_id=i.tenant_id, project_id=i.project_id,
        title=i.title, description=i.description,
        status=i.status, priority=i.priority, target_release=i.target_release
    )



# --------- Phase 10: LangGraph run endpoints ---------
class GraphStartBody(BaseModel):
    force_qa_fail: bool = False
    max_qa_loops: int = 2
    inject_failures: Dict[str, int] = {}
    stop_after: Optional[str] = None

@app.post("/runs/{run_id}/graph/start")
def graph_start(run_id: str, body: GraphStartBody, db: Session = Depends(get_db)):
    # Runs a full graph pass synchronously (stub LLMs). Returns final state.
    # Pre-checks for clearer errors and to avoid misclassifying downstream ValueErrors
    run = db.get(RunDB, run_id)
    if not run:
        raise HTTPException(404, "run not found")
    if not run.roadmap_item_id:
        raise HTTPException(400, "run has no roadmap_item_id")
    try:
        result = start_graph_run(
            db,
            run_id,
            force_qa_fail=body.force_qa_fail,
            max_qa_loops=body.max_qa_loops,
            inject_failures=body.inject_failures,
            stop_after=body.stop_after,
        )
    except ValueError as e:
        # Treat unexpected ValueErrors during execution as bad request
        raise HTTPException(400, str(e))
    except Exception as e:
        # mark run as partial on failure (retry exhausted or unexpected error)
        try:
            run = db.get(RunDB, run_id)
            if run:
                run.status = "partial"
                db.commit()
        except Exception:
            db.rollback()
        last = repo_get_last(db, run_id)
        failed_step = last.step_name if last else "unknown"
        attempts = last.attempt if last else 3
        # Ensure a failed attempt is recorded if none exists yet for this step
        detail = {
            "run_id": run_id,
            "status": "failed",
            "failed_step": failed_step,
            "attempts": attempts,
            "error": str(e),
        }
        raise HTTPException(400, detail=detail)
    return {
        "run_id": run_id,
        "status": "completed",
        "nodes_run": result.get("history", []),
        "qa_attempts": result.get("qa_attempts", 0),
        "tests_result": result.get("tests_result", {}),
        "pr_info": result.get("pr_info", {}),
    }

@app.get("/runs/{run_id}/graph/state")
def graph_state(run_id: str, db: Session = Depends(get_db)):
    # Prefer in-memory, but if persisted history is ahead (e.g., after resume), reconcile from DB
    state = get_graph_state(run_id)
    try:
        last = repo_get_last(db, run_id)
        if last:
            mem_hist = (state or {}).get("history", []) if isinstance(state, dict) else []
            if (not mem_hist) or (mem_hist and mem_hist[-1] != last.step_name):
                db_state, _ = resume_from_last(db, run_id)
                if db_state:
                    set_graph_state(run_id, db_state)
                    return db_state
    except Exception:
        pass
    if not state:
        raise HTTPException(404, "no graph state recorded for this run")
    return state

# --------- Phase 11: resume + history ---------
class GraphResumeBody(BaseModel):
    inject_failures: Dict[str, int] = {}
    stop_after: Optional[str] = None

@app.post("/runs/{run_id}/graph/resume")
def graph_resume(run_id: str, body: GraphResumeBody, db: Session = Depends(get_db)):
    # Load last persisted state and resume execution from next step
    run = db.get(RunDB, run_id)
    if not run:
        raise HTTPException(404, "run not found")

    # Determine if anything is left using persisted history (authoritative: last row)
    last_row = repo_get_last(db, run_id)
    if last_row and last_row.step_name == "release" and last_row.status == "ok":
        raise HTTPException(400, detail={"error": "Nothing to resume"})

    state, next_idx = resume_from_last(db, run_id)
    order = ["product", "design", "research", "cto_plan", "engineer", "qa", "release"]
    hist = state.get("history", [])
    # If computed next index is out of range, nothing to resume
    if next_idx >= len(order):
        raise HTTPException(400, detail={"error": "Nothing to resume"})
    
    # Only allow resume from paused/partial; but only after we verified nothing to resume
    if run.status not in ("paused", "partial"):
        raise HTTPException(400, detail={"error": f"Cannot resume from status '{run.status}'"})
    state["inject_failures"] = dict(body.inject_failures or {})
    state["stop_after"] = body.stop_after
    # Ensure continuation runs fully (clear any prior early stop)
    if "early_stop" in state:
        state.pop("early_stop", None)
    # Default QA controls if missing
    state.setdefault("force_qa_fail", False)
    state.setdefault("max_qa_loops", 2)
    state["resume_pointer"] = len(state.get("history", []))
    state["resume_consumed"] = 0
    state["next_step_index"] = next_idx

    # Transition to running for this resume pass
    run.status = "running"
    db.commit()
    app_graph = build_graph(db)
    try:
        result = app_graph.invoke(state, config={"configurable": {"thread_id": run_id}})
    except Exception as e:
        # mark run as partial on failure during resume
        try:
            run = db.get(RunDB, run_id)
            if run:
                run.status = "partial"
                db.commit()
        except Exception:
            db.rollback()
        last = repo_get_last(db, run_id)
        failed_step = last.step_name if last else "unknown"
        attempts = last.attempt if last else 3
        detail = {
            "run_id": run_id,
            "status": "failed",
            "failed_step": failed_step,
            "attempts": attempts,
            "error": str(e),
        }
        raise HTTPException(400, detail=detail)
    # Update in-memory state for visibility
    try:
        set_graph_state(run_id, result)
    except Exception:
        pass
    # Update DB run status based on result
    try:
        hist2 = result.get("history", [])
        is_completed = len(hist2) > 0 and hist2[-1] == "release"
        run.status = "succeeded" if is_completed else "paused"
        db.commit()
    except Exception:
        db.rollback()
    return {
        "run_id": run_id,
        "status": "completed",
        "nodes_run": result.get("history", []),
        "qa_attempts": result.get("qa_attempts", 0),
        "tests_result": result.get("tests_result", {}),
        "pr_info": result.get("pr_info", {}),
    }

@app.get("/runs/{run_id}/graph/history")
def graph_history(run_id: str, db: Session = Depends(get_db)):
    hist = repo_get_history(db, run_id)
    return [
        {
            "step_index": h["step_index"],
            "step_name": h["step_name"],
            "status": h["status"],
            "attempt": h["attempt"],
            "created_at": h["created_at"],
            "error": h["error"],
            "duration_ms": h.get("duration_ms", 0),
        }
        for h in hist
    ]

# --------- Phase 14: Observability & Telemetry ---------
@app.get("/runs/{run_id}/metrics")
def graph_metrics(run_id: str, db: Session = Depends(get_db)):
    # Returns deterministic per-run metrics computed from persisted graph states
    run = db.get(RunDB, run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return compute_run_metrics(db, run_id)


# --------- Phase 16: Minimal Founder Cockpit UI ---------
def _github_write_enabled() -> bool:
    try:
        val = os.getenv("GITHUB_WRITE_ENABLED", "1").strip().lower()
    except Exception:
        val = "1"
    return val not in {"0", "false", "no"}


@app.get("/ui", response_class=HTMLResponse)
def ui_index():
    # Minimal landing page with nav to run view
    html = f"""
    <!doctype html>
    <html lang=\"en\">
    <head>
      <meta charset=\"utf-8\" />
      <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
      <title>Founder Cockpit · AI‑CSuite</title>
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 24px; color: #111; }}
        h1 {{ margin-top: 0; }}
        .card {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; max-width: 720px; }}
        .row {{ display: flex; gap: 8px; align-items: center; }}
        input[type=text] {{ padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 6px; width: 360px; }}
        button {{ padding: 8px 12px; border: 1px solid #d1d5db; background: #f9fafb; border-radius: 6px; cursor: pointer; }}
        button:hover {{ background: #f3f4f6; }}
      </style>
    </head>
    <body>
      <h1>Founder Cockpit</h1>
      <p><a href=\"/ui/blueprints\">Create from Blueprint</a></p>
      <p><a id=\"navPostmortems\" href=\"/ui/postmortems\">Postmortems</a></p>
      <p><a id=\"navScheduler\" href=\"/ui/scheduler\">Scheduler</a></p>
      <p><a id=\"navIntegrations\" href=\"/ui/integrations\">Integrations</a></p>
      <div class=\"card\">
        <p>Enter a run id to view timeline, statuses, and approvals.</p>
        <div class=\"row\">
          <input id=\"runId\" type=\"text\" placeholder=\"run id (UUID)\" />
          <button id=\"goBtn\">Open</button>
        </div>
        <p style=\"margin-top:8px;\">Example: <code>/ui/run/&lt;run_id&gt;</code></p>
      </div>
      <script>
        document.getElementById('goBtn').addEventListener('click', function() {{
          var v = document.getElementById('runId').value.trim();
          if (v) window.location.href = '/ui/run/' + encodeURIComponent(v);
        }});
      </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/ui/integrations", response_class=HTMLResponse)
def ui_integrations():
    # Minimal deterministic UI for partner integrations
    html = """
    <!doctype html>
    <html lang=\"en\">
    <head>
      <meta charset=\"utf-8\" />
      <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
      <title>Founder Cockpit · Integrations</title>
      <style>
        body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 24px; color: #111; }
        h1 { margin: 0 0 12px 0; }
        table { border-collapse: collapse; width: 100%; max-width: 900px; }
        th, td { border: 1px solid #e5e7eb; padding: 6px 8px; text-align: left; }
        .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin: 8px 0; }
        .muted { color: #6b7280; font-size: 12px; }
        button { padding: 8px 12px; border: 1px solid #d1d5db; background: #f9fafb; border-radius: 6px; cursor: pointer; }
        button:hover { background: #f3f4f6; }
        input[type=text] { padding: 6px 8px; border: 1px solid #d1d5db; border-radius: 6px; }
      </style>
    </head>
    <body>
      <a href=\"/ui\" class=\"muted\">← Back</a>
      <h1>Partners</h1>
      <div class=\"row\">
        <button id=\"refreshBtn\">Refresh</button>
        <button id=\"tickBtn\">Tick</button>
        <span id=\"msg\" class=\"muted\"></span>
      </div>
      <table>
        <thead>
          <tr><th>partner_id</th><th>circuit_state</th><th>rate_remaining</th><th>calls</th><th>retries</th><th>failures</th><th>deduped</th></tr>
        </thead>
        <tbody id=\"tbody\"></tbody>
      </table>
      <div class=\"row\" style=\"margin-top:12px;\">
        <label class=\"muted\">Call: partner_id</label>
        <input id=\"pid\" type=\"text\" value=\"mock_echo\" />
        <label class=\"muted\">op</label>
        <input id=\"op\" type=\"text\" value=\"echo\" />
        <label class=\"muted\">payload</label>
        <input id=\"payload\" type=\"text\" value=\"{\\\"payload\\\":\\\"hi\\\"}\" />
        <label class=\"muted\">idempotency_key</label>
        <input id=\"ikey\" type=\"text\" />
        <button id=\"callBtn\">Call</button>
      </div>
      <pre id=\"out\" class=\"muted\" style=\"white-space:pre-wrap;\"></pre>
      <script>
      (function() {
        function setText(id, txt) { var el = document.getElementById(id); if (el) el.textContent = txt; }
        function render(list) {
          var tb = document.getElementById('tbody');
          tb.innerHTML='';
          var items = Array.isArray(list) ? list.slice() : [];
          // deterministic order guaranteed from API; iterate in order
          items.forEach(function(it) {
            var tr = document.createElement('tr');
            var cols = [it.partner_id, it.state.circuit_state, String(it.state.rate_remaining), String(it.counters.calls), String(it.counters.retries), String(it.counters.failures), String(it.counters.deduped)];
            cols.forEach(function(text){ var td = document.createElement('td'); td.textContent = text; tr.appendChild(td); });
            tb.appendChild(tr);
          });
        }
        function refresh() { fetch('/integrations/partners').then(r => r.json()).then(render).catch(function() { setText('msg','Load error'); }); }
        document.getElementById('refreshBtn').addEventListener('click', refresh);
        document.getElementById('tickBtn').addEventListener('click', function() {
          setText('msg','Ticking…');
          fetch('/integrations/partners/tick', { method: 'POST' }).then(r => r.json()).then(function() { setText('msg','Ticked'); refresh(); }).catch(function() { setText('msg','Tick failed'); });
        });
        document.getElementById('callBtn').addEventListener('click', function() {
          var pid = document.getElementById('pid').value.trim();
          var op = document.getElementById('op').value.trim();
          var payloadText = document.getElementById('payload').value.trim();
          var ikey = document.getElementById('ikey').value.trim();
          var body = { op: op };
          try { body.payload = payloadText ? JSON.parse(payloadText) : null; } catch(e) { body.payload = null; }
          if (ikey) body.idempotency_key = ikey;
          setText('msg','Calling…');
          fetch('/integrations/partners/' + encodeURIComponent(pid) + '/call', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
            .then(function(r) { return r.json().then(function(j) { return { status: r.status, json: j }; }); })
            .then(function(res) {
              try { document.getElementById('out').textContent = JSON.stringify(res.json); } catch(e) { document.getElementById('out').textContent = String(res.json); }
              setText('msg', res.status === 200 ? 'OK' : 'Error');
              refresh();
            }).catch(function() { setText('msg','Call failed'); });
        });
        refresh();
      })();
      </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
@app.get("/ui/blueprints", response_class=HTMLResponse)
def ui_blueprints():
    # Deterministic create-from-blueprint page; client fetches existing endpoints only
    write_enabled = _github_write_enabled()
    dry_banner = "" if write_enabled else "<div id=\"dry\" style=\"background:#fff7ed;border:1px solid #fdba74;color:#9a3412;padding:8px 12px;border-radius:6px;margin:0 0 12px 0;\">Dry‑run: GitHub writes disabled (GITHUB_WRITE_ENABLED=0). Owner/Repo optional.</div>"
    try:
        items = _bp_registry().list()
    except Exception:
        items = []
    ids = sorted([getattr(b, "id", str(b)) for b in items])
    options_html = "".join([f"<option value=\"{bid}\">{bid}</option>" for bid in ids])
    html = f"""
    <!doctype html>
    <html lang=\"en\">
    <head>
      <meta charset=\"utf-8\" />
      <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
      <title>Founder Cockpit · Create from Blueprint</title>
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 24px; color: #111; }}
        h1 {{ margin: 0 0 12px 0; }}
        .card {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; max-width: 760px; }}
        .row {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
        label {{ font-size: 12px; color: #374151; display:block; margin: 8px 0 4px 0; }}
        select, input[type=text] {{ padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 6px; min-width: 240px; }}
        button {{ padding: 8px 12px; border: 1px solid #d1d5db; background: #f9fafb; border-radius: 6px; cursor: pointer; }}
        button:hover {{ background: #f3f4f6; }}
        button[disabled] {{ opacity: 0.5; cursor: not-allowed; }}
        .muted {{ color: #6b7280; font-size: 12px; }}
      </style>
    </head>
    <body>
      <a href=\"/ui\" class=\"muted\">← Back</a>
      <h1>Create from Blueprint</h1>
      {dry_banner}
      <div class=\"card\">
        <div class=\"row\" style=\"margin-bottom:8px;\">
          <div>
            <label for=\"bpSelect\">Blueprint</label>
            <select id=\"bpSelect\">{options_html}</select>
          </div>
          <div>
            <label for=\"owner\">Target Owner</label>
            <input id=\"owner\" type=\"text\" placeholder=\"org or user\" />
          </div>
          <div>
            <label for=\"repo\">Target Repo Name</label>
            <input id=\"repo\" type=\"text\" placeholder=\"repo\" />
          </div>
          <div>
            <label for=\"branch\">Default Branch</label>
            <input id=\"branch\" type=\"text\" value=\"main\" />
          </div>
        </div>
        <div class=\"row\">
          <button id=\"scaffoldBtn\">Scaffold</button>
          <span id=\"msg\" class=\"muted\"></span>
        </div>
        <pre id=\"result\" class=\"muted\" style=\"white-space:pre-wrap;margin-top:8px;\"></pre>
      </div>

      <script>
      (function() {{
        var sel = document.getElementById('bpSelect');
        var msg = document.getElementById('msg');
        var out = document.getElementById('result');
        function loadBlueprints() {{
          fetch('/blueprints').then(r => r.json()).then(list => {{
            if (!Array.isArray(list)) list = [];
            list.sort(function(a,b) {{ return String(a.id).localeCompare(String(b.id)); }});
            sel.innerHTML = '';
            list.forEach(function(b) {{
              var opt = document.createElement('option');
              opt.value = b.id; opt.textContent = b.id; sel.appendChild(opt);
            }});
          }}).catch(function() {{ /* keep server-rendered options */ }});
        }}
        document.getElementById('scaffoldBtn').addEventListener('click', function() {{
          var id = sel.value;
          var owner = document.getElementById('owner').value.trim();
          var repo = document.getElementById('repo').value.trim();
          var branch = document.getElementById('branch').value.trim() || 'main';
          msg.textContent = 'Submitting…'; out.textContent='';
          fetch('/app-factory/scaffold', {{
            method: 'POST',
            headers: {{ 'content-type': 'application/json' }},
            body: JSON.stringify({{
              blueprint_id: id,
              target: {{ mode: 'existing_repo', owner: owner || null, name: repo || null, default_branch: branch }}
            }})
          }}).then(r => r.json()).then(res => {{
            try {{ out.textContent = JSON.stringify(res); }} catch(e) {{ out.textContent = String(res); }}
            msg.textContent = (res && res.op_id) ? 'Done' : 'Completed';
          }}).catch(function() {{ msg.textContent = 'Error'; }});
        }});
        loadBlueprints();
      }})();
      </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/ui/run/{run_id}", response_class=HTMLResponse)
def ui_run(run_id: str, dry_run: bool | None = Query(default=None)):
    # Render a minimal, deterministic run view; hydrate via existing JSON endpoints
    write_enabled = _github_write_enabled() if dry_run is None else (not dry_run)
    dry_banner = "" if write_enabled else "<div id=\"dry\" style=\"background:#fff7ed;border:1px solid #fdba74;color:#9a3412;padding:8px 12px;border-radius:6px;margin:0 0 12px 0;\">Dry‑run: GitHub writes disabled (GITHUB_WRITE_ENABLED=0)</div>"
    approve_disabled = "" if write_enabled else " disabled"
    merge_disabled = "" if write_enabled else " disabled"

    html = f"""
    <!doctype html>
    <html lang=\"en\">
    <head>
      <meta charset=\"utf-8\" />
      <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
      <title>Founder Cockpit · Run {run_id}</title>
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 24px; color: #111; }}
        h1 {{ margin: 0 0 12px 0; }}
        .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
        .card {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; }}
        .muted {{ color: #6b7280; font-size: 12px; }}
        button {{ padding: 8px 12px; border: 1px solid #d1d5db; background: #f9fafb; border-radius: 6px; cursor: pointer; }}
        button:hover {{ background: #f3f4f6; }}
        button[disabled] {{ opacity: 0.5; cursor: not-allowed; }}
        code {{ background: #f3f4f6; padding: 1px 4px; border-radius: 4px; }}
        ul {{ margin: 8px 0; padding-left: 18px; }}
        .row {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
      </style>
    </head>
    <body>
      <a href=\"/ui\" class=\"muted\">← Back</a>
      <h1>Run <code>{run_id}</code></h1>
      {dry_banner}
      <div id=\"app\" data-run-id=\"{run_id}\" data-write-enabled=\"{1 if write_enabled else 0}\"></div>

      <div class=\"grid\">
        <div class=\"card\">
          <h3 style=\"margin:0 0 8px 0;\">Run Status</h3>
          <div id=\"runSummary\" class=\"muted\">Loading…</div>
          <div id="budget" class="muted" style="margin-top:6px;">Budget: Loading…</div>
          <div class="row" style="margin-top:8px;">
            <button id="refreshBtn">Refresh</button>
            <button id="approveBtn"{approve_disabled}>Approve</button>
            <button id="mergeBtn"{merge_disabled}>Merge</button>
            <button id=\"computeBudgetBtn\">Compute Budget</button>
          </div>
          <div id="actionMsg" class="muted" style="margin-top:8px;"></div>
        </div>

        <div class=\"card\">
          <h3 style=\"margin:0 0 8px 0;\">PR Statuses</h3>
          <div id=\"ghStatuses\" class=\"muted\">Loading…</div>
        </div>

        <div class=\"card\" style=\"grid-column: span 2;\">
          <h3 style=\"margin:0 0 8px 0;\">Timeline</h3>
          <div id=\"timeline\" class=\"muted\">Loading…</div>
        </div>

        <div class=\"card\" style=\"grid-column: span 2;\">
          <h3 style=\"margin:0 0 8px 0;\">Metrics</h3>
          <div id=\"metrics\" class=\"muted\">Loading…</div>
        </div>

        <div class=\"card\" style=\"grid-column: span 2;\">
          <h3 style=\"margin:0 0 8px 0;\">Alerts</h3>
          <div id=\"alerts\" class=\"muted\">Loading…</div>
        </div>
      </div>

      <script>
      (function() {{
        var root = document.getElementById('app');
        var runId = root.getAttribute('data-run-id');
        var writeEnabled = root.getAttribute('data-write-enabled') === '1';
        var msg = document.getElementById('actionMsg');
        function setText(id, text) {{ var el = document.getElementById(id); if (el) el.textContent = text; }}
        function fmtDate(s) {{ try {{ return new Date(s).toLocaleString(); }} catch(e) {{ return s; }} }}

        function refresh() {{
          fetch('/runs/' + runId).then(r => r.json()).then(data => {{
            setText('runSummary', 'Status: ' + data.status + ' · Created: ' + fmtDate(data.created_at));
          }}).catch(() => setText('runSummary', 'Run not found'));

          fetch('/integrations/github/pr/' + runId + '/statuses').then(r => r.json()).then(st => {{
            var lines = [];
            if (Array.isArray(st.statuses)) {{
              st.statuses.forEach(function(s) {{ lines.push(s.context + ': ' + s.state); }});
            }}
            if (st.can_merge !== undefined) lines.push('Can merge: ' + st.can_merge);
            document.getElementById('ghStatuses').textContent = lines.join(' \u00b7 ') || 'No PR recorded';
          }}).catch(() => setText('ghStatuses', 'No PR recorded or error'));

          fetch('/runs/' + runId + '/graph/history').then(r => r.json()).then(hist => {{
            if (!Array.isArray(hist) || hist.length === 0) {{ setText('timeline', 'No history yet'); return; }}
            var txt = hist.map(function(h) {{ return h.step_name + ' (' + h.status + ' #' + h.attempt + ')'; }}).join(' \u2192 ');
            setText('timeline', txt);
          }}).catch(() => setText('timeline', 'No history yet'));

          fetch('/runs/' + runId + '/metrics').then(r => r.json()).then(m => {{
            try {{ setText('metrics', JSON.stringify(m)); }} catch(e) {{ setText('metrics', 'n/a'); }}
          }}).catch(() => setText('metrics', 'n/a'));

          fetch('/integrations/budget/' + runId).then(r => r.json()).then(b => {{
            var pct = Math.round((b.totals && b.totals.pct_used ? b.totals.pct_used*100 : 0));
            var limit = (b.totals && b.totals.budget_cents ? ('$' + (b.totals.budget_cents/100).toFixed(2)) : 'n/a');
            setText('budget', 'Budget: ' + pct + '% of ' + limit + ' · Status: ' + b.status);
          }}).catch(() => setText('budget', 'Budget: n/a'));

          fetch('/integrations/alerts/' + runId).then(r => r.json()).then(a => {{
            var parts = [];
            parts.push('Status: ' + a.status);
            if (Array.isArray(a.alerts) && a.alerts.length > 0) {{
              parts.push('Active: ' + a.alerts.map(function(x) {{ return x.type + (x.key ? '(' + x.key + ')' : ''); }}).join(', '));
            }} else {{
              parts.push('Active: none');
            }}
            setText('alerts', parts.join(' · '));
          }}).catch(() => setText('alerts', 'n/a'));
        }}

        document.getElementById('refreshBtn').addEventListener('click', refresh);
        document.getElementById('approveBtn').addEventListener('click', function() {{
          if (!writeEnabled) {{ msg.textContent = 'Dry‑run: GitHub writes disabled (GITHUB_WRITE_ENABLED=0)'; return; }}
          msg.textContent = 'Approving…';
          fetch('/integrations/github/pr/' + runId + '/approve', {{ method: 'POST' }})
            .then(r => r.json()).then(() => {{ msg.textContent = 'Approved'; refresh(); }})
            .catch(() => {{ msg.textContent = 'Approve failed'; }});
        }});
        document.getElementById('mergeBtn').addEventListener('click', function() {{
          if (!writeEnabled) {{ msg.textContent = 'Dry‑run: GitHub writes disabled (GITHUB_WRITE_ENABLED=0)'; return; }}
          msg.textContent = 'Merging…';
          fetch('/integrations/github/pr/' + runId + '/merge', {{ method: 'POST' }})
            .then(r => r.json()).then(res => {{ msg.textContent = res && res.merged ? 'Merged' : 'Merge attempted'; refresh(); }})
            .catch(() => {{ msg.textContent = 'Merge failed'; }});
        }});

        document.getElementById('computeBudgetBtn').addEventListener('click', function() {{
          msg.textContent = 'Computing budget…';
          fetch('/integrations/budget/' + runId + '/compute', {{
            method: 'POST',
            headers: {{ 'content-type': 'application/json' }},
            body: JSON.stringify({{ warn_pct: 0.8, block_pct: 1.0, rate: {{ usd_per_1k_tokens: 0.01 }} }})
          }})
            .then(r => r.json()).then(() => {{ msg.textContent = 'Budget computed'; refresh(); }})
            .catch(() => {{ msg.textContent = 'Budget compute failed'; }});
        }});

        // Initial load
        refresh();
      }})();
      </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/ui/scheduler", response_class=HTMLResponse)
def ui_scheduler():
    # Minimal deterministic UI for scheduler
    html = """
    <!doctype html>
    <html lang=\"en\">
    <head>
      <meta charset=\"utf-8\" />
      <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
      <title>Founder Cockpit · Scheduler</title>
      <style>
        body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 24px; color: #111; }
        h1 { margin: 0 0 12px 0; }
        table { border-collapse: collapse; width: 100%; max-width: 900px; }
        th, td { border: 1px solid #e5e7eb; padding: 6px 8px; text-align: left; }
        .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin: 8px 0; }
        .muted { color: #6b7280; font-size: 12px; }
        button { padding: 8px 12px; border: 1px solid #d1d5db; background: #f9fafb; border-radius: 6px; cursor: pointer; }
        button:hover { background: #f3f4f6; }
        button[disabled] { opacity: 0.5; cursor: not-allowed; }
        .card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; max-width: 960px; }
      </style>
    </head>
    <body>
      <a href=\"/ui\" class=\"muted\">← Back</a>
      <h1>Scheduler</h1>
      <div class=\"row\">
        <button id=\"refreshBtn\">Refresh</button>
        <button id=\"stepBtn\">Step</button>
        <span id=\"msg\" class=\"muted\"></span>
      </div>
      <div class=\"card\">
        <h3 style=\"margin:0 0 8px 0;\">Policy</h3>
        <div id=\"policy\" class=\"muted\">Loading…</div>
      </div>
      <div class=\"card\" style=\"margin-top:12px;\">
        <h3 style=\"margin:0 0 8px 0;\">Stats</h3>
        <div id=\"stats\" class=\"muted\">Loading…</div>
      </div>
      <div class=\"card\" style=\"margin-top:12px;\">
        <h3 style=\"margin:0 0 8px 0;\">Queue</h3>
        <div id=\"counts\" class=\"muted\">Loading…</div>
        <table id=\"queue\">
          <thead>
            <tr><th>Index</th><th>Run ID</th><th>Tenant</th><th>Priority</th><th>State</th></tr>
          </thead>
          <tbody id=\"tbody\"></tbody>
        </table>
      </div>
      <script>
      (function() {
        function setText(id, txt) { var el = document.getElementById(id); if (el) el.textContent = txt; }
        function loadPolicy() {
          fetch('/scheduler/policy').then(r => r.json()).then(p => {
            setText('policy', 'enabled=' + p.enabled + ' · global_concurrency=' + p.global_concurrency + ' · tenant_max_active=' + p.tenant_max_active + ' · queue_max=' + p.queue_max);
          }).catch(() => setText('policy', 'n/a'));
        }
        function loadStats() {
          fetch('/scheduler/stats').then(r => r.json()).then(s => {
            setText('stats', 'leases=' + (s.leases||0) + ' · skipped_due_to_quota=' + (s.skipped_due_to_quota||0) + ' · completed=' + (s.completed||0));
          }).catch(() => setText('stats', 'n/a'));
        }
        function loadQueue() {
          fetch('/scheduler/queue').then(r => r.json()).then(q => {
            setText('counts', 'queued=' + q.queued + ' · active=' + q.active + ' · completed=' + q.completed);
            var tb = document.getElementById('tbody');
            tb.innerHTML = '';
            var items = Array.isArray(q.items) ? q.items.slice() : [];
            // stable sort already from API; re-affirm deterministic order
            items.forEach(function(it, idx) {
              var tr = document.createElement('tr');
              var tds = [String(idx), String(it.run_id), String(it.tenant_id), String(it.priority), String(it.state)];
              tds.forEach(function(text){ var td = document.createElement('td'); td.textContent = text; tr.appendChild(td); });
              tb.appendChild(tr);
            });
            var stepBtn = document.getElementById('stepBtn');
            stepBtn.disabled = (items.length === 0);
          }).catch(() => setText('counts', 'n/a'));
        }
        function refreshAll() { loadPolicy(); loadStats(); loadQueue(); }
        document.getElementById('refreshBtn').addEventListener('click', refreshAll);
        document.getElementById('stepBtn').addEventListener('click', function() {
          var msg = document.getElementById('msg');
          msg.textContent = 'Stepping…';
          fetch('/scheduler/step', { method: 'POST' }).then(r => r.json()).then(res => {
            msg.textContent = res.leased ? ('Leased ' + res.leased) : (res.status || 'done');
            refreshAll();
          }).catch(() => { msg.textContent = 'Step failed'; });
        });
        refreshAll();
      })();
      </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

# --------- Phase 30: Postmortems Cockpit ---------
@app.get("/ui/postmortems", response_class=HTMLResponse)
def ui_postmortems():
    html = """
    <!doctype html>
    <html lang=\"en\">
    <head>
      <meta charset=\"utf-8\" />
      <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
      <title>Founder Cockpit · Postmortems</title>
      <style>
        body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 24px; color: #111; }
        h1 { margin: 0 0 12px 0; }
        table { border-collapse: collapse; width: 100%; max-width: 960px; }
        th, td { border: 1px solid #e5e7eb; padding: 6px 8px; text-align: left; }
        .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin: 8px 0; }
        .muted { color: #6b7280; font-size: 12px; }
        button { padding: 8px 12px; border: 1px solid #d1d5db; background: #f9fafb; border-radius: 6px; cursor: pointer; }
        button:hover { background: #f3f4f6; }
        input[type=text] { padding: 6px 8px; border: 1px solid #d1d5db; border-radius: 6px; }
      </style>
    </head>
    <body>
      <a href=\"/ui\" class=\"muted\">← Back</a>
      <h1>Postmortems</h1>
      <div class=\"row\">
        <button id=\"refreshBtn\">Refresh</button>
        <label class=\"muted\">Generate: run_id</label>
        <input id=\"genRun\" type=\"text\" />
        <button id=\"genBtn\">Generate</button>
        <label class=\"muted\">Ingest to KB: run_id</label>
        <input id=\"kbRun\" type=\"text\" />
        <button id=\"kbBtn\">Ingest</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>run_id</th>
            <th>status</th>
            <th>failed_step</th>
            <th>retries</th>
            <th>alerts_count</th>
            <th>budget_status</th>
            <th>tags</th>
          </tr>
        </thead>
        <tbody id=\"tbody\"></tbody>
      </table>
      <script>
      (function() {
        function render(list) {
          var tb = document.getElementById('tbody');
          tb.innerHTML='';
          var items = Array.isArray(list) ? list.slice() : [];
          items.forEach(function(it) {
            var tr = document.createElement('tr');
            var cols = [it.run_id, it.status, (it.failed_step||'-'), String(it.retries||0), String(it.alerts_count||0), (it.budget_status||'n/a'), (Array.isArray(it.tags)?it.tags.join(','):'')];
            cols.forEach(function(text){ var td = document.createElement('td'); td.textContent = text; tr.appendChild(td); });
            tb.appendChild(tr);
          });
        }
        function load() {
          // Fetch search results; then hydrate rows with full artifact
          fetch('/postmortems/search?q=').then(r=>r.json()).then(function(results){
            // Base rows with minimal fields
            var out = results.map(function(r){ return { run_id: r.run_id, status: r.status, failed_step: '-', retries: 0, alerts_count: 0, budget_status: 'n/a', tags: r.tags }; });
            var pending = out.length;
            if (pending === 0) { render(out); return; }
            out.forEach(function(row, idx){
              fetch('/postmortems/' + encodeURIComponent(row.run_id))
                .then(function(resp){ return resp.ok ? resp.json() : null; })
                .then(function(art){
                  if (art && art.meta) {
                    out[idx].status = art.meta.status || row.status;
                    out[idx].retries = art.meta.retries || 0;
                    out[idx].failed_step = art.meta.failed_step || '-';
                    var ac = (((art.alerts||{}).counts||{}).total)||0;
                    out[idx].alerts_count = ac;
                    out[idx].budget_status = (art.budget||{}).status || 'n/a';
                    out[idx].tags = art.tags||row.tags||[];
                  }
                }).catch(function(){ /* keep defaults */ })
                .finally(function(){ pending -= 1; if (pending === 0) render(out); });
            });
          }).catch(function(){ render([]); });
        }
        document.getElementById('refreshBtn').addEventListener('click', load);
        document.getElementById('genBtn').addEventListener('click', function(){
          var v = document.getElementById('genRun').value.trim();
          if (!v) return;
          fetch('/postmortems/' + encodeURIComponent(v) + '/generate', { method: 'POST' })
            .then(function(){ load(); }).catch(function(){});
        });
        document.getElementById('kbBtn').addEventListener('click', function(){
          var v = document.getElementById('kbRun').value.trim();
          if (!v) return;
          fetch('/postmortems/' + encodeURIComponent(v) + '/ingest-kb', { method: 'POST' })
            .then(function(){ load(); }).catch(function(){});
        });
        load();
      })();
      </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
