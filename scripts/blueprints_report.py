#!/usr/bin/env python3
from __future__ import annotations

import fnmatch
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


# Ensure orchestrator app modules are importable (local, in-process)
_APPS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "orchestrator"))
if _APPS_DIR not in sys.path:
    sys.path.insert(0, _APPS_DIR)

try:
    from orchestrator.blueprints.models import BlueprintManifest  # type: ignore
    from orchestrator.db import SessionLocal, Base, engine  # type: ignore
    from orchestrator.kb import ingest_text as kb_ingest  # type: ignore
    from orchestrator.security import apply_redaction, mask_dict  # type: ignore
except Exception:
    # Allow running without orchestrator imports in minimal contexts
    class _Dummy:
        pass

    def kb_ingest(*args: Any, **kwargs: Any) -> int:  # type: ignore
        return 0

    def apply_redaction(text: str, mode: str = "strict") -> str:  # type: ignore
        return text

    def mask_dict(obj: Any, mode: str = "strict") -> Any:  # type: ignore
        return obj

    SessionLocal = _Dummy  # type: ignore
    Base = _Dummy  # type: ignore
    engine = _Dummy  # type: ignore


def _get_env_bool(name: str, default: bool) -> bool:
    s = os.getenv(name)
    if s is None:
        return default
    return s.strip() not in {"0", "false", "False", "no", ""}


def _now_iso() -> str:
    from datetime import datetime, timezone

    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _write_json_sorted(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _match_any(name: str, patterns: List[str]) -> bool:
    for p in patterns:
        if fnmatch.fnmatch(name, p):
            return True
    return False


def _ingest_kb_if_enabled(report: Dict[str, Any]) -> None:
    if not _get_env_bool("BLUEPRINTS_WRITE_KB", False):
        return
    # Deterministic, redacted summary rows
    rows: List[Dict[str, Any]] = []
    for b in report.get("blueprints", []):
        row = {
            "id": b.get("id"),
            "version": b.get("version"),
            "a11y_min": (b.get("quality_gates") or {}).get("a11y_min"),
            "e2e_cov_min": (b.get("quality_gates") or {}).get("e2e_cov_min"),
            "perf_budget_ms": (b.get("quality_gates") or {}).get("perf_budget_ms"),
        }
        rows.append(mask_dict(row))
    text = json.dumps({"rows": rows}, sort_keys=True)
    text = apply_redaction(text, mode="strict")
    # Ensure tables exist for standalone script usage
    try:
        Base.metadata.create_all(bind=engine)  # type: ignore
    except Exception:
        pass
    db = SessionLocal()  # type: ignore
    try:
        kb_ingest(
            db,
            tenant_id=os.getenv("TENANT_ID", "00000000-0000-0000-0000-000000000000"),
            project_id=os.getenv("PROJECT_ID", "00000000-0000-0000-0000-000000000000"),
            kind="blueprints-report",
            ref_id="latest",
            text=text,
        )  # type: ignore
        try:
            db.commit()  # type: ignore
        except Exception:
            pass
    finally:
        try:
            db.close()  # type: ignore
        except Exception:
            pass


def _discover_blueprints(bp_dir: Path) -> List[Tuple[Path, Dict[str, Any]]]:
    out: List[Tuple[Path, Dict[str, Any]]] = []
    files = sorted([p for p in bp_dir.glob("*.json") if p.is_file()], key=lambda p: p.name)
    for f in files:
        if f.name == "report.json":
            continue
        try:
            data = _read_json(f)
        except Exception:
            # Malformed JSON manifests are treated as manifest errors later (on validation)
            data = {"__invalid_json__": True}
        out.append((f, data))
    return out


def main() -> int:
    if not _get_env_bool("BLUEPRINTS_ENABLED", True):
        outdir = Path(os.getenv("BLUEPRINTS_OUTDIR", "blueprints"))
        _write_json_sorted(outdir / "report.json", {"blueprints": [], "summary": {"count": 0, "failed": 0, "finished_at": "", "passed": 0, "started_at": ""}})
        return 0

    bp_dir = Path("blueprints").resolve()
    outdir = Path(os.getenv("BLUEPRINTS_OUTDIR", "blueprints")).resolve()
    include = [s.strip() for s in os.getenv("BLUEPRINTS_INCLUDE", "").split(",") if s.strip()]
    exclude = [s.strip() for s in os.getenv("BLUEPRINTS_EXCLUDE", "").split(",") if s.strip()]

    discovered = _discover_blueprints(bp_dir)

    manifests: List[Tuple[str, Dict[str, Any]]] = []  # (id, raw)
    manifest_errors = 0
    duplicate_ids: set[str] = set()
    seen_ids: set[str] = set()

    for path, raw in discovered:
        # Skip by filename if excludes match the implied id in filename prefix
        try_id = str((raw or {}).get("id") or path.stem)
        if include and (not _match_any(try_id, include)):
            continue
        if exclude and _match_any(try_id, exclude):
            continue
        # Validate with Pydantic
        try:
            mf = BlueprintManifest(**raw)  # type: ignore
            bid = mf.id
            raw_id = bid
        except Exception:
            manifest_errors += 1
            # Use filename stem as id for dedup accounting to avoid false duplicates
            raw_id = try_id
            bid = None  # type: ignore
        # Duplicate id check if valid id resolved
        if raw_id in seen_ids:
            duplicate_ids.add(raw_id)
        seen_ids.add(raw_id)
        if bid:
            # Only include valid manifests in report list
            manifests.append((bid, raw))

    # Sort by id for report
    manifests.sort(key=lambda t: t[0])

    blueprints_list: List[Dict[str, Any]] = []
    for bid, raw in manifests:
        qg = raw.get("quality_gates") or {}
        entry = {
            "id": str(bid),
            "name": str(raw.get("name")),
            "version": str(raw.get("version")),
            "capabilities": list(raw.get("capabilities") or []),
            "quality_gates": {
                "a11y_min": int(qg.get("a11y_min")),
                "e2e_cov_min": float(qg.get("e2e_cov_min")),
                "perf_budget_ms": int(qg.get("perf_budget_ms")),
            },
        }
        # normalize capabilities ordering deterministically
        entry["capabilities"] = sorted(entry["capabilities"], key=lambda x: str(x))
        blueprints_list.append(entry)

    # Gating evaluation: pass if thresholds present (validated) and within model constraints
    passed = len(blueprints_list)
    failed = 0
    # If duplicates or manifest_errors occurred, treat as failures for exit code
    if manifest_errors or duplicate_ids:
        failed = 1  # collapse to non-zero; details not required in report
    count = len(blueprints_list)

    # Determine timestamps with idempotency w.r.t core content
    started_at = _now_iso()
    finished_at = started_at
    report_core = {
        "blueprints": blueprints_list,
        "summary": {
            "count": count,
            "failed": failed,
            "passed": passed if failed == 0 else max(0, passed - failed),
        },
    }

    report_path = outdir / "report.json"
    if report_path.exists():
        try:
            prev = _read_json(report_path)
            prev_core = {
                "blueprints": prev.get("blueprints", []),
                "summary": {
                    "count": (prev.get("summary") or {}).get("count"),
                    "failed": (prev.get("summary") or {}).get("failed"),
                    "passed": (prev.get("summary") or {}).get("passed"),
                },
            }
            if json.dumps(prev_core, sort_keys=True) == json.dumps(report_core, sort_keys=True):
                started_at = str((prev.get("summary") or {}).get("started_at") or started_at)
                finished_at = str((prev.get("summary") or {}).get("finished_at") or finished_at)
        except Exception:
            pass

    report: Dict[str, Any] = {
        "blueprints": blueprints_list,
        "summary": {
            "count": count,
            "failed": failed,
            "passed": passed if failed == 0 else max(0, passed - failed),
            "started_at": started_at,
            "finished_at": finished_at,
        },
    }

    _write_json_sorted(report_path, report)

    # Optional local-only KB ingestion
    _ingest_kb_if_enabled(report)

    # Exit non-zero on gate violations or manifest errors
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())


