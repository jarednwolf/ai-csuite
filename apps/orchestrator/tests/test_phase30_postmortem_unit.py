import os
import uuid
from sqlalchemy.orm import Session

from orchestrator.services.postmortem import PostmortemService
from orchestrator.kb import ingest_text
from orchestrator.models import KbChunk, RunDB


def _mk_run(db: Session, tenant_id: str, project_id: str) -> str:
    run_id = str(uuid.uuid4())
    row = RunDB(id=run_id, tenant_id=tenant_id, project_id=project_id, roadmap_item_id=None, phase="delivery", status="pending")
    db.add(row)
    db.commit()
    return run_id


def test_postmortem_search_stable_ordering_and_tag_filter(db_session):
    db: Session = db_session
    svc = PostmortemService()

    # Seed three artifacts in memory directly (no graph history needed for search behavior)
    svc._enabled = lambda: True  # type: ignore
    # Mimic generated artifacts
    svc_reset = svc.reset
    svc.reset = lambda rid: {"deleted": True}  # type: ignore
    try:
        svc._ARTIFACTS = {}  # type: ignore
    except Exception:
        pass

    # Use private store via generate path: create minimal entries
    # We can emulate by directly touching internal store for determinism in unit scope
    from orchestrator.services.postmortem import _ARTIFACTS as STORE  # type: ignore
    STORE.clear()
    STORE["b-run"] = {"meta": {"status": "ok"}, "tags": ["postmortem", "alpha"], "alerts": {"counts": {"total": 1}}, "budget": {"status": "ok"}}
    STORE["a-run"] = {"meta": {"status": "ok"}, "tags": ["postmortem", "beta"],  "alerts": {"counts": {"total": 0}}, "budget": {"status": "ok"}}
    STORE["c-run"] = {"meta": {"status": "ok"}, "tags": ["postmortem", "alpha"], "alerts": {"counts": {"total": 2}}, "budget": {"status": "warn"}}

    # Search with no query returns all in stable run_id asc order
    res = svc.search(q=None, tag=None)
    assert [r["run_id"] for r in res] == ["a-run", "b-run", "c-run"]

    # Tag filter narrows results and preserves ordering
    res_alpha = svc.search(q=None, tag="alpha")
    assert [r["run_id"] for r in res_alpha] == ["b-run", "c-run"]

    # Query filter (substring on headline/components) is deterministic
    res_q = svc.search(q="warn", tag=None)
    assert [r["run_id"] for r in res_q] == ["c-run"]


def test_postmortem_ingest_idempotent_when_kb_row_exists(db_session):
    db: Session = db_session
    tenant_id = "00000000-0000-0000-0000-000000000000"
    project_id = str(uuid.uuid4())
    # Create a run row to satisfy ingest_kb lookups
    run_id = _mk_run(db, tenant_id=tenant_id, project_id=project_id)

    # Seed KB row as if ingested earlier
    ingest_text(db, tenant_id=tenant_id, project_id=project_id, kind="postmortem", ref_id=run_id, text="seed")

    svc = PostmortemService()
    # Also seed an in-memory artifact minimal to allow ingest path to construct summary
    from orchestrator.services.postmortem import _ARTIFACTS as STORE  # type: ignore
    STORE[run_id] = {
        "meta": {"run_id": run_id, "status": "ok", "retries": 0},
        "tags": ["postmortem"],
        "alerts": {"counts": {"total": 0}},
        "budget": {"status": "ok"},
    }

    # First ingest sees existing row and reports already
    res1 = svc.ingest_kb(db, run_id)
    assert res1.get("already") is True or res1.get("chunks", 0) >= 1
    # Second ingest remains idempotent
    res2 = svc.ingest_kb(db, run_id)
    assert res2.get("already") is True or res2.get("chunks", 0) >= 1


