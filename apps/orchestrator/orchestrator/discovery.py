import uuid
from sqlalchemy.orm import Session
from .models import Project, RoadmapItem, PRD, DesignCheck, ResearchNote
from .agents import product as product_agent
from .agents import design as design_agent
from .agents import research as research_agent
from .kb import search as kb_search, ingest_text as kb_ingest

def _next_version(db: Session, tenant_id: str, project_id: str, item_id: str) -> str:
    # very simple vN incrementer for PRD only (others don't track versions yet)
    last = (
        db.query(PRD)
        .filter(PRD.tenant_id == tenant_id, PRD.project_id == project_id, PRD.roadmap_item_id == item_id)
        .order_by(PRD.created_at.desc())
        .first()
    )
    if not last:
        return "v0"
    try:
        n = int((last.version or "v0").lstrip("v"))
        return f"v{n+1}"
    except Exception:
        return "v1"

def upsert_discovery_artifacts(db: Session, tenant_id: str, project_id: str, roadmap_item_id: str, *, force: bool = False):
    """
    Ensure PRD/Design/Research exist. If 'force' is True, create a new version instead of no-op.
    Returns: dict(created={prd,design,research}, ids={prd,design,research})
    """
    created = {"prd": False, "design": False, "research": False}
    ids = {"prd": None, "design": None, "research": None}

    proj = db.get(Project, project_id)
    item = db.get(RoadmapItem, roadmap_item_id)
    if not proj or not item:
        return {"created": created, "ids": ids}

    # Pull related context from KB
    related = kb_search(db, tenant_id, project_id, f"{proj.name} {item.title}", k=3)
    related_snippets = [r["text"] for r in related]

    # PRD
    prd = (
        db.query(PRD)
        .filter(PRD.tenant_id == tenant_id, PRD.project_id == project_id, PRD.roadmap_item_id == roadmap_item_id)
        .order_by(PRD.created_at.desc())
        .first()
    )
    if not prd or force:
        prd_json = product_agent.draft_prd(proj.name, item.title, references=related_snippets)
        prd = PRD(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            project_id=project_id,
            roadmap_item_id=roadmap_item_id,
            version=_next_version(db, tenant_id, project_id, roadmap_item_id) if force else (prd.version if prd else "v0"),
            prd_json=prd_json,
        )
        db.add(prd)
        db.commit()
        kb_ingest(db, tenant_id, project_id, kind="prd", ref_id=prd.id, text=f"{prd_json}")
        created["prd"] = True
    ids["prd"] = prd.id if prd else None

    # Design check
    design = (
        db.query(DesignCheck)
        .filter(DesignCheck.tenant_id == tenant_id, DesignCheck.project_id == project_id, DesignCheck.roadmap_item_id == roadmap_item_id)
        .order_by(DesignCheck.created_at.desc())
        .first()
    )
    if not design or force:
        d = design_agent.review_ui(proj.name, item.title)
        design = DesignCheck(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id, project_id=project_id, roadmap_item_id=roadmap_item_id,
            passes=d["passes"], heuristics_score=d["heuristics_score"], a11y_notes=d["a11y_notes"]
        )
        db.add(design)
        db.commit()
        kb_ingest(db, tenant_id, project_id, kind="design", ref_id=design.id, text=f"{d}")
        created["design"] = True
    ids["design"] = design.id if design else None

    # Research note
    research = (
        db.query(ResearchNote)
        .filter(ResearchNote.tenant_id == tenant_id, ResearchNote.project_id == project_id, ResearchNote.roadmap_item_id == roadmap_item_id)
        .order_by(ResearchNote.created_at.desc())
        .first()
    )
    if not research or force:
        r = research_agent.synthesize(proj.name, item.title, related_snippets=related_snippets)
        research = ResearchNote(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id, project_id=project_id, roadmap_item_id=roadmap_item_id,
            summary=r["summary"], evidence=r["evidence"]
        )
        db.add(research)
        db.commit()
        kb_ingest(db, tenant_id, project_id, kind="research", ref_id=research.id, text=f"{r}")
        created["research"] = True
    ids["research"] = research.id if research else None

    return {"created": created, "ids": ids}

def dor_check(db: Session, tenant_id: str, project_id: str, roadmap_item_id: str):
    """(Unchanged) See earlier implementation."""
    from .models import PRD, DesignCheck, ResearchNote  # local import to avoid cycles
    missing = []
    details = {}

    prd = (
        db.query(PRD)
        .filter(PRD.tenant_id == tenant_id, PRD.project_id == project_id, PRD.roadmap_item_id == roadmap_item_id)
        .order_by(PRD.created_at.desc())
        .first()
    )
    design = (
        db.query(DesignCheck)
        .filter(DesignCheck.tenant_id == tenant_id, DesignCheck.project_id == project_id, DesignCheck.roadmap_item_id == roadmap_item_id)
        .order_by(DesignCheck.created_at.desc())
        .first()
    )
    research = (
        db.query(ResearchNote)
        .filter(ResearchNote.tenant_id == tenant_id, ResearchNote.project_id == project_id, ResearchNote.roadmap_item_id == roadmap_item_id)
        .order_by(ResearchNote.created_at.desc())
        .first()
    )

    if not prd:
        missing.append("prd")
    else:
        ac = prd.prd_json.get("acceptance_criteria") if isinstance(prd.prd_json, dict) else None
        if not ac or len(ac) == 0:
            missing.append("prd.acceptance_criteria")
        details["prd_id"] = prd.id

    if not design:
        missing.append("design")
    else:
        if not design.passes:
            missing.append("design.passes")
        details["design_id"] = design.id

    if not research:
        missing.append("research")
    else:
        if not research.summary:
            missing.append("research.summary")
        details["research_id"] = research.id

    return (len(missing) == 0), missing, details


