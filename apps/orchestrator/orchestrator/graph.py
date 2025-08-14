import os
from sqlalchemy.orm import Session
from .models import RunDB
from .discovery import upsert_discovery_artifacts, dor_check

def ensure_discovery_and_gate(db: Session, run: RunDB) -> tuple[bool, list[str]]:
    """
    Always (idempotently) create missing PRD/Design/Research artifacts before DoR.
    This prevents 'blocked' runs due to empty discovery.
    Controlled by AUTO_ENSURE_DISCOVERY (default: enabled).
    """
    if not run.roadmap_item_id:
        return True, []

    auto_ensure = os.getenv("AUTO_ENSURE_DISCOVERY", "1").strip().lower() not in {"0", "false", "no"}
    if auto_ensure:
        # Fill gaps only (force=False) — keeps existing versions unless refreshed explicitly elsewhere
        upsert_discovery_artifacts(db, run.tenant_id, run.project_id, run.roadmap_item_id, force=False)

    ok, missing, _ = dor_check(db, run.tenant_id, run.project_id, run.roadmap_item_id)
    return ok, missing

def run_delivery_cycle(db: Session, run_id: str) -> None:
    # Minimal stub: update status and return; your agent pipeline can expand here.
    db_obj = db.get(RunDB, run_id)
    if db_obj:
        db_obj.status = "succeeded"
        db.commit()


