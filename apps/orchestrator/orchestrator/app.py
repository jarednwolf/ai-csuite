
from fastapi import FastAPI, HTTPException, Depends, Query
from sqlalchemy.orm import Session
import uuid, datetime as dt
from typing import Optional, List
import os

from .db import Base, engine, get_db
from .models import RunDB, Project, RoadmapItem, PRD, DesignCheck, ResearchNote, KbChunk, PullRequest
from .schemas import (
    RunCreate, RunRead,
    ProjectCreate, ProjectRead, ProjectUpdate,  # NEW
    RoadmapItemCreate, RoadmapItemRead, RoadmapItemUpdate,
    PRDRead, DesignCheckRead, ResearchNoteRead, DiscoveryStatus,
    KbIngest, KbSearchResult, GithubVerify, PRRead
)
from .graph import run_delivery_cycle, ensure_discovery_and_gate
from .discovery import dor_check, upsert_discovery_artifacts  # ensure import
from .kb import ingest_text as kb_ingest, search as kb_search
from .integrations.github import verify_repo_access, open_pr_for_run
from .integrations.github import upsert_pr_summary_comment_for_run
from .webhooks import router as webhooks_router
from .integrations.github import ensure_and_update_for_branch_event
from .integrations.github import approve_pr_for_run, refresh_dor_status_for_run, statuses_for_run, merge_pr_for_run, set_status_for_run

app = FastAPI(title="AI C-suite Orchestrator (Phase 8)")

# --- Startup: ensure tables exist ---
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

app.include_router(webhooks_router)

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
    # return updated status summary
    return statuses_for_run(db, run_id)

@app.post("/integrations/github/pr/{run_id}/refresh-status")
def github_pr_refresh(run_id: str, db: Session = Depends(get_db)):
    # Re-evaluate DoR and update status; return updated statuses
    res = refresh_dor_status_for_run(db, run_id)
    if "error" in res or "skipped" in res:
        raise HTTPException(400, res.get("error") or res.get("skipped"))
    return statuses_for_run(db, run_id)

@app.post("/integrations/github/pr/{run_id}/merge")
def github_pr_merge(run_id: str, method: str = Query("squash"), db: Session = Depends(get_db)):
    res = merge_pr_for_run(db, run_id, method=method)
    if res.get("blocked"):
        raise HTTPException(400, f"merge blocked: {res.get('reason')}")
    if "error" in res or "skipped" in res:
        raise HTTPException(400, res.get("error") or res.get("skipped"))
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

