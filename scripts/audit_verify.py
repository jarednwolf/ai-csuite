#!/usr/bin/env python3
import json
import os
from typing import Dict, List

from sqlalchemy import create_engine, text


def _db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    host = os.getenv("POSTGRES_HOST")
    if host:
        user = os.getenv("POSTGRES_USER", "csuite")
        password = os.getenv("POSTGRES_PASSWORD", "csuite")
        db = os.getenv("POSTGRES_DB", "csuite")
        return f"postgresql+psycopg://{user}:{password}@{host}:5432/{db}"
    return "sqlite:///./dev.db"


REQUIRED_EVENTS = [
    "github.approve",
    "github.merge",
    "preview.deploy",
    "preview.smoke",
    "budget.compute",
    "budget.get",
    "budget.reset",
    "webhook.github",
]


def main() -> int:
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "compliance", "audit_report.json"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    engine = create_engine(_db_url(), echo=False, future=True)
    report: Dict[str, object] = {"ok": True, "missing_events": [], "rows": []}
    code = 0
    try:
        with engine.begin() as conn:
            # Verify table exists
            # Portable existence check for SQLite and Postgres
            has_table_sqlite = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_logs'"))
            has_table = has_table_sqlite.fetchone()
            if not has_table:
                try:
                    has_table_pg = conn.execute(text("SELECT to_regclass('public.audit_logs')"))
                    row = has_table_pg.fetchone()
                    has_table = (row and row[0] is not None)
                except Exception:
                    has_table = False
            if not has_table:
                report["ok"] = False
                report["reason"] = "audit_logs table missing"
                code = 1
            else:
                # Fetch recent events deterministically
                rows = conn.execute(text("""
                    SELECT event_type, run_id, project_id, actor, request_id, ts
                    FROM audit_logs
                    ORDER BY ts ASC, event_type ASC, request_id ASC
                """)).fetchall()
                for r in rows:
                    report["rows"].append({
                        "event_type": r[0],
                        "run_id": r[1],
                        "project_id": r[2],
                        "actor": r[3],
                        "request_id": r[4],
                        "ts": str(r[5]),
                    })
                # Verify presence of required event types (may be subset if flows unexercised)
                got = {row[0] for row in rows}
                missing = [e for e in REQUIRED_EVENTS if e not in got]
                # Not hard fail if AUDIT_ENABLED=0
                if os.getenv("AUDIT_ENABLED", "1").strip().lower() in {"0","false","no"}:
                    report["skipped"] = True
                else:
                    if missing:
                        report["ok"] = False
                        report["missing_events"] = missing
                        code = 1
    except Exception as e:
        report["ok"] = False
        report["error"] = str(e)
        code = 1

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())


