#!/usr/bin/env python3
import json
import os
import sys
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Tuple


# Orchestrator local-only helpers for optional KB ingest
_APPS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "orchestrator"))
if _APPS_DIR not in sys.path:
    sys.path.insert(0, _APPS_DIR)
try:
    from orchestrator.security import apply_redaction, mask_dict  # type: ignore
    from orchestrator.db import SessionLocal, Base, engine  # type: ignore
    from orchestrator.kb import ingest_text as kb_ingest  # type: ignore
except Exception:
    # Allow running without orchestrator import in minimal contexts
    def apply_redaction(text: str, mode: str = "strict") -> str:  # type: ignore
        return text

    def mask_dict(obj: Any, mode: str = "strict") -> Any:  # type: ignore
        return obj

    class _Dummy:
        pass
    SessionLocal = _Dummy  # type: ignore
    Base = _Dummy  # type: ignore
    engine = _Dummy  # type: ignore
    def kb_ingest(*args: Any, **kwargs: Any) -> int:  # type: ignore
        return 0


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_sorted(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, sort_keys=True) + "\n", encoding="utf-8")


def _get_env_bool(name: str, default: bool) -> bool:
    s = os.getenv(name)
    if s is None:
        return default
    return s.strip() not in ("0", "false", "False", "no", "")


def _env_str(name: str, default: str) -> str:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip() or default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash_core(obj: Any) -> str:
    b = json.dumps(obj, sort_keys=True).encode("utf-8")
    return hashlib.sha256(b).hexdigest()


def _parse_fixture(path: Path, fallback_steps: List[int]) -> List[Dict[str, Any]]:
    d = _read_json(path)
    steps = d.get("steps")
    if isinstance(steps, list) and steps:
        out: List[Dict[str, Any]] = []
        for s in steps:
            try:
                percent = int(s.get("percent"))
                m = s.get("metrics") or {}
                er = float(m.get("error_rate"))
                p95 = int(m.get("p95_ms"))
                out.append({"percent": percent, "metrics": {"error_rate": er, "p95_ms": p95}})
            except Exception:
                continue
        # Sort by percent deterministically
        out.sort(key=lambda z: int(z.get("percent")))
        return out
    # Aggregate metrics case
    m = d.get("metrics") or {}
    try:
        er = float(m.get("error_rate"))
        p95 = int(m.get("p95_ms"))
    except Exception:
        # Invalid fixture, treat as empty
        return []
    out = [{"percent": int(p), "metrics": {"error_rate": er, "p95_ms": p95}} for p in sorted(set(fallback_steps))]
    out.sort(key=lambda z: int(z.get("percent")))
    return out


def _ingest_kb_if_enabled(report: Dict[str, Any]) -> None:
    if not _get_env_bool("RELEASE_WRITE_KB", False):
        return
    tenant_id = os.getenv("TENANT_ID", "00000000-0000-0000-0000-000000000000")
    project_id = os.getenv("PROJECT_ID", "00000000-0000-0000-0000-000000000000")
    summary = report.get("summary") or {}
    env = report.get("env") or {}
    safe = {
        "env": env.get("id"),
        "score": summary.get("score"),
        "status": summary.get("status"),
        "passed": summary.get("passed"),
        "failed": summary.get("failed"),
        "threshold_err": summary.get("threshold_err"),
        "threshold_p95": summary.get("threshold_p95"),
    }
    safe = mask_dict(safe)
    text = json.dumps(safe, sort_keys=True)
    text = apply_redaction(text, mode="strict")
    try:
        Base.metadata.create_all(bind=engine)  # type: ignore
    except Exception:
        pass
    db = SessionLocal()  # type: ignore
    try:
        kb_ingest(db, tenant_id=tenant_id, project_id=project_id, kind="release-report", ref_id="latest", text=text)  # type: ignore
        db.commit()  # type: ignore
    finally:
        try:
            db.close()  # type: ignore
        except Exception:
            pass


def main() -> int:
    if not _get_env_bool("RELEASE_ENABLED", True):
        # Graceful no-op writing a minimal report
        outdir = Path("deployments")
        _write_json_sorted(outdir / "report.json", {"env": {"id": "", "target": ""}, "steps": [], "summary": {"failed": 0, "finished_at": "", "passed": 0, "score": 0.0, "started_at": "", "status": "pass", "threshold_err": 0.0, "threshold_p95": 0}})
        return 0

    release_env = _env_str("RELEASE_ENV", _env_str("IAC_ENV", "staging"))
    fixtures_raw = [s.strip() for s in _env_str("RELEASE_FIXTURES", "deployments/fixtures/canary_ok.json").split(",") if s.strip()]
    fixtures = sorted([Path(p) for p in fixtures_raw], key=lambda x: x.as_posix())
    step_list = [int(s.strip()) for s in _env_str("ROLL_OUT_STEPS", "10,50,100").split(",") if s.strip()]
    thr_err = _env_float("ROLL_OUT_THRESH_ERR", 0.02)
    thr_p95 = _env_int("ROLL_OUT_THRESH_P95", 800)

    # Build combined steps (concatenate in fixture path order)
    steps: List[Dict[str, Any]] = []
    for f in fixtures:
        if f.exists():
            steps.extend(_parse_fixture(f, step_list))

    # De-duplicate by percent keeping first occurrence and sort deterministically
    dedup: Dict[int, Dict[str, Any]] = {}
    for s in steps:
        pct = int(s.get("percent"))
        if pct not in dedup:
            dedup[pct] = s
    steps = [dedup[p] for p in sorted(dedup.keys())]

    # Evaluate gating per step
    evaluated_steps: List[Dict[str, Any]] = []
    failed = 0
    for s in steps:
        m = s.get("metrics") or {}
        er = float(m.get("error_rate") or 0.0)
        p95 = int(m.get("p95_ms") or 0)
        reason = "ok"
        status = "pass"
        err_exceeded = er > thr_err
        p95_exceeded = p95 > thr_p95
        if err_exceeded and p95_exceeded:
            status = "fail"
            reason = "threshold_both"
        elif err_exceeded:
            status = "fail"
            reason = "threshold_err"
        elif p95_exceeded:
            status = "fail"
            reason = "threshold_p95"
        if status == "fail":
            failed += 1
        evaluated_steps.append({
            "percent": int(s.get("percent")),
            "metrics": {"error_rate": er, "p95_ms": p95},
            "status": status,
            "reason": reason,
        })

    passed = int(len(evaluated_steps) - failed)
    score = 0.0 if len(evaluated_steps) == 0 else round(passed / len(evaluated_steps), 4)
    overall_status = "pass" if failed == 0 else "fail"

    started_at = _now_iso()
    finished_at = started_at

    report_core = {
        "env": {"id": release_env, "target": release_env},
        "steps": evaluated_steps,
        "summary": {
            "passed": passed,
            "failed": failed,
            "score": score,
            "threshold_err": thr_err,
            "threshold_p95": thr_p95,
            "status": overall_status,
        },
    }

    outdir = Path("deployments")
    report_path = outdir / "report.json"
    if report_path.exists():
        try:
            prev = _read_json(report_path)
            prev_core = {
                "env": {"id": (prev.get("env") or {}).get("id"), "target": (prev.get("env") or {}).get("target")},
                "steps": prev.get("steps", []),
                "summary": {
                    "passed": (prev.get("summary") or {}).get("passed"),
                    "failed": (prev.get("summary") or {}).get("failed"),
                    "score": (prev.get("summary") or {}).get("score"),
                    "threshold_err": (prev.get("summary") or {}).get("threshold_err"),
                    "threshold_p95": (prev.get("summary") or {}).get("threshold_p95"),
                    "status": (prev.get("summary") or {}).get("status"),
                },
            }
            if json.dumps(prev_core, sort_keys=True) == json.dumps(report_core, sort_keys=True):
                started_at = str((prev.get("summary") or {}).get("started_at") or started_at)
                finished_at = str((prev.get("summary") or {}).get("finished_at") or finished_at)
        except Exception:
            pass

    report = {
        "env": {"id": release_env, "target": release_env},
        "steps": evaluated_steps,
        "summary": {
            "status": overall_status,
            "passed": passed,
            "failed": failed,
            "score": score,
            "threshold_err": thr_err,
            "threshold_p95": thr_p95,
            "started_at": started_at,
            "finished_at": finished_at,
        },
    }

    _write_json_sorted(report_path, report)

    # Optional local-only KB ingestion
    _ingest_kb_if_enabled(report)

    return 0 if overall_status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
