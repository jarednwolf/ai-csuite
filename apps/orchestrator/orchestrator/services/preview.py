from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Tuple

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Session
from sqlalchemy import String, Integer, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base
from ..integrations.github import _write_enabled as _gh_write_enabled
from ..integrations.github import (
    set_preview_status_for_branch,
    upsert_marker_comment_for_branch,
    build_pr_summary_md,
)
from ..integrations.github import _parse_repo_url  # reuse parser if needed
from ..discovery import dor_check
from ..models import RunDB, Project, RoadmapItem, PullRequest


def _env_true(key: str, default: str = "1") -> bool:
    try:
        val = os.getenv(key, default).strip().lower()
    except Exception:
        val = default
    return val not in {"0", "false", "no"}


def _now() -> datetime:
    return datetime.utcnow()


def _slug(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "preview"


class PreviewDeployRow(Base):
    __tablename__ = "preview_deploys"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64))
    owner: Mapped[str] = mapped_column(String(128), default="")
    repo: Mapped[str] = mapped_column(String(200), default="")
    branch: Mapped[str] = mapped_column(String(200), default="")
    preview_url: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|success|failure
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("run_id", name="uq_preview_run_id"),
    )


def ensure_tables(db: Session) -> None:
    Base.metadata.create_all(bind=db.get_bind())


def _compose_preview_url(base_url: Optional[str], branch: str, run_id: str) -> str:
    base = (base_url or os.getenv("PREVIEW_BASE_URL", "http://preview.local")).rstrip("/")
    segment = _slug(branch or run_id)
    return f"{base}/{segment}"


def _dry_run() -> bool:
    return not _gh_write_enabled()


@dataclass
class DeployInput:
    run_id: str
    owner: str
    repo: str
    branch: str
    base_url: Optional[str] = None
    force: bool = False


class PreviewService:
    def __init__(self) -> None:
        pass

    def deploy(self, db: Session, payload: DeployInput) -> Dict[str, object]:
        if not _env_true("PREVIEW_ENABLED", "1"):
            raise ValueError("preview disabled (PREVIEW_ENABLED=0)")
        ensure_tables(db)

        # Compose URL deterministically
        preview_url = _compose_preview_url(payload.base_url, payload.branch, payload.run_id)

        # Idempotent upsert by run_id
        from uuid import uuid4
        row = db.query(PreviewDeployRow).filter(PreviewDeployRow.run_id == payload.run_id).first()
        if row:
            row.owner = payload.owner or row.owner
            row.repo = payload.repo or row.repo
            row.branch = payload.branch or row.branch
            row.preview_url = preview_url
            row.status = "pending"
            row.attempts = int(row.attempts or 0) + 1
            row.error = None
            row.updated_at = _now()
            db.commit()
        else:
            row = PreviewDeployRow(
                id=str(uuid4()),
                run_id=payload.run_id,
                owner=payload.owner,
                repo=payload.repo,
                branch=payload.branch,
                preview_url=preview_url,
                status="pending",
                attempts=1,
                error=None,
                updated_at=_now(),
            )
            db.add(row)
            db.commit()

        # Set GitHub status to pending (dry-run respected inside helper)
        gh_res = set_preview_status_for_branch(
            payload.owner,
            payload.repo,
            payload.branch,
            state="pending",
            description="Preview deploying",
            target_url=preview_url,
        )

        result: Dict[str, object] = {
            "run_id": payload.run_id,
            "preview_url": preview_url,
            "status": "pending",
            "attempts": row.attempts,
            "updated_at": row.updated_at.isoformat() + "Z",
        }
        if isinstance(gh_res, dict) and (gh_res.get("dry_run") or gh_res.get("skipped")):
            # surface simulation/skips for tests
            result["github"] = {"status": gh_res}
        return result

    def smoke(self, db: Session, run_id: str, *, timeout_ms: int = 1000, inject_fail: bool = False) -> Dict[str, object]:
        if not _env_true("PREVIEW_ENABLED", "1"):
            raise ValueError("preview disabled (PREVIEW_ENABLED=0)")
        ensure_tables(db)

        row = db.query(PreviewDeployRow).filter(PreviewDeployRow.run_id == run_id).first()
        if not row:
            raise LookupError("preview not found for run_id")

        # Deterministic smoke: success unless injection flag requested
        ok = not inject_fail
        new_status = "success" if ok else "failure"
        row.status = new_status
        row.attempts = int(row.attempts or 0) + 1
        row.error = ("injected failure" if not ok else None)
        row.updated_at = _now()
        db.commit()

        # Update GH status for branch
        gh_res = set_preview_status_for_branch(
            row.owner,
            row.repo,
            row.branch,
            state=new_status,
            description=("Preview healthy" if ok else "Preview smoke failed"),
            target_url=row.preview_url,
        )

        # Compose a preview section for summary upsert; prefer enriching the canonical summary
        # using existing builder when we have project/item context.
        body = None
        try:
            run = db.get(RunDB, row.run_id)
            project = db.get(Project, run.project_id) if run else None
            item = db.get(RoadmapItem, run.roadmap_item_id) if (run and run.roadmap_item_id) else None
            if run and project:
                ok_dor, missing, _ = dor_check(db, run.tenant_id, run.project_id, run.roadmap_item_id)
                base_dir = f"docs/roadmap/{(run.roadmap_item_id or run.id)[:8]}-{_slug(item.title if item else 'change')}"
                base = build_pr_summary_md(
                    project_name=project.name,
                    item_title=(item.title if item else "Change"),
                    branch=row.branch,
                    dor_pass=ok_dor,
                    missing=missing,
                    owner=row.owner,
                    repo=row.repo.split("/")[-1] if "/" in row.repo else row.repo,
                    base_dir=base_dir,
                )
                # Append preview section
                preview_lines = [
                    "### Preview",
                    f"- URL: {row.preview_url}",
                    f"- Smoke: {'✅ Success' if ok else '❌ Failure'} @ {row.updated_at.isoformat()}Z",
                ]
                if _dry_run():
                    preview_lines.append("")
                    preview_lines.append("_Dry‑run: GitHub writes disabled (GITHUB_WRITE_ENABLED=0)_")
                body = base + "\n" + "\n".join(preview_lines) + "\n"
        except Exception:
            body = None
        if body is None:
            # Fallback minimal body with marker
            preview_lines = [
                "### Preview",
                f"- URL: {row.preview_url}",
                f"- Smoke: {'✅ Success' if ok else '❌ Failure'} @ {row.updated_at.isoformat()}Z",
            ]
            if _dry_run():
                preview_lines.append("")
                preview_lines.append("_Dry‑run: GitHub writes disabled (GITHUB_WRITE_ENABLED=0)_")
            preview_section = "\n".join(preview_lines) + "\n"
            body = "\n".join([
                f"### AI‑CSuite Summary — Preview",
                "",
                preview_section,
                f"<!-- ai-csuite:summary:{row.branch} -->",
                "",
            ])

        upsert_res = upsert_marker_comment_for_branch(row.owner, row.repo, row.branch, body)

        result: Dict[str, object] = {
            "ok": ok,
            "run_id": run_id,
            "preview_url": row.preview_url,
            "status": new_status,
            "attempts": row.attempts,
            "updated_at": row.updated_at.isoformat() + "Z",
        }
        # Surface simulation outputs for tests: statuses list and summary body
        statuses_list = []
        if isinstance(gh_res, dict):
            if gh_res.get("dry_run"):
                statuses_list.append({"context": "ai-csuite/preview-smoke", "state": new_status})
            elif gh_res.get("skipped"):
                statuses_list.append({"context": "ai-csuite/preview-smoke", "state": new_status, "skipped": True})
        if isinstance(upsert_res, dict) and (upsert_res.get("dry_run") or upsert_res.get("skipped")):
            result["summary"] = body
        if statuses_list:
            result["statuses"] = statuses_list
        return result

    def get_info(self, db: Session, run_id: str) -> Dict[str, object]:
        ensure_tables(db)
        row = db.query(PreviewDeployRow).filter(PreviewDeployRow.run_id == run_id).first()
        if not row:
            raise LookupError("preview not found for run_id")
        return {
            "run_id": run_id,
            "preview_url": row.preview_url,
            "status": row.status,
            "attempts": int(row.attempts or 0),
            "updated_at": row.updated_at.isoformat() + "Z",
            "branch": row.branch,
        }


