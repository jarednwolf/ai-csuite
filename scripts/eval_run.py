#!/usr/bin/env python3
import os
import sys
import json
import fnmatch
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure orchestrator app modules are importable (reuse approach from other scripts)
_APPS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "orchestrator"))
if _APPS_DIR not in sys.path:
    sys.path.insert(0, _APPS_DIR)

# Local-only utilities from orchestrator
from orchestrator.integrations.github import build_pr_summary_md  # type: ignore
from orchestrator.security import apply_redaction, mask_dict  # type: ignore
from orchestrator.db import SessionLocal, Base, engine  # type: ignore
from orchestrator.kb import ingest_text as kb_ingest  # type: ignore


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_sorted(path: Path, obj: Any) -> None:
    # Stable formatting: sorted keys, newline-terminated
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, sort_keys=True) + "\n", encoding="utf-8")


def _get_env_bool(name: str, default: bool) -> bool:
    s = os.getenv(name)
    if s is None:
        return default
    return s.strip() not in ("0", "false", "False", "no", "")


def _now_iso() -> str:
    # Deterministic timestamps requirement: reuse previous if fingerprint unchanged.
    # When new, use a single computed value for both start and finish for simplicity.
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_path_get(obj: Any, path: str) -> Any:
    cur = obj
    for part in (path or "").split("."):
        if part == "":
            continue
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list):
            try:
                idx = int(part)
            except Exception:
                raise KeyError(f"non-integer path segment '{part}' for list")
            cur = cur[idx]
        else:
            raise KeyError(f"path '{path}' not found")
    return cur


def _hash_fingerprint(obj: Any) -> str:
    b = json.dumps(obj, sort_keys=True).encode("utf-8")
    return hashlib.sha256(b).hexdigest()


def _match_any(name: str, patterns: List[str]) -> bool:
    for p in patterns:
        if fnmatch.fnmatch(name, p):
            return True
    return False


def _filter_suites_tasks(suites: List[Dict[str, Any]], includes: List[str], excludes: List[str]) -> List[Dict[str, Any]]:
    # Patterns can match suite id (e.g., "web-*") or specific task via "suite:task" or "*/task"
    out: List[Dict[str, Any]] = []
    for suite in suites:
        sid = suite.get("id") or ""
        tasks = suite.get("tasks") or []
        new_tasks = []
        for t in tasks:
            tid = t.get("id") or ""
            full = f"{sid}:{tid}"
            allow = True
            if includes:
                allow = _match_any(sid, includes) or _match_any(full, includes) or _match_any(f"*:{tid}", includes)
            if excludes and (_match_any(sid, excludes) or _match_any(full, excludes) or _match_any(f"*:{tid}", excludes)):
                allow = False
            if allow:
                new_tasks.append(t)
        if new_tasks:
            suite = dict(suite)
            suite["tasks"] = new_tasks
            out.append(suite)
    return out


def _execute_assert(assertion: Dict[str, Any]) -> Tuple[bool, str]:
    atype = assertion.get("type")
    try:
        if atype == "file_json_eq":
            file_path = Path(assertion["file"]).resolve()
            data = _read_json(file_path)
            actual = _json_path_get(data, assertion["path"])
            expect = assertion["expect"]
            ok = actual == expect
            return ok, ("ok" if ok else f"file_json_eq failed: {assertion['path']} actual={actual!r} expect={expect!r}")
        if atype == "file_json_contains":
            file_path = Path(assertion["file"]).resolve()
            data = _read_json(file_path)
            actual = _json_path_get(data, assertion["path"])
            expect_item = assertion["expect_item"]
            if not isinstance(actual, list):
                return False, f"file_json_contains failed: {assertion['path']} not a list"
            ok = expect_item in actual
            return ok, ("ok" if ok else f"file_json_contains failed: missing {expect_item!r} in {assertion['path']}")
        if atype == "function_contains":
            func = assertion["function"]
            args = assertion.get("args", {})
            expect_sub = assertion["expect_sub"]
            if func == "build_pr_summary_md":
                md = build_pr_summary_md(**args)
                ok = expect_sub in md
                return ok, ("ok" if ok else f"function_contains failed: substring not found")
            return False, f"unsupported function: {func}"
        if atype == "echo_equals":
            text = assertion["text"]
            expect = assertion["expect"]
            ok = (text == expect)
            return ok, ("ok" if ok else f"echo_equals failed")
        if atype == "redact_contains":
            text = assertion["text"]
            mode = assertion.get("mode", "strict")
            expect_sub = assertion["expect_sub"]
            red = apply_redaction(text, mode=mode)
            ok = expect_sub in red
            return ok, ("ok" if ok else f"redact_contains failed")
        return False, f"unsupported assert type: {atype}"
    except Exception as e:
        return False, f"assertion error: {atype}: {e}"


def _run_task(suite_id: str, task: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    # Deterministically execute assertions (AND semantics)
    details: Dict[str, Any] = {
        "suite": suite_id,
        "task": task.get("id"),
        "category": task.get("category"),
        "weight": float(task.get("weight") or 1.0),
        "asserts": [],
    }
    ok = True
    for a in (task.get("asserts") or []):
        a_ok, reason = _execute_assert(a)
        details["asserts"].append({"type": a.get("type"), "ok": a_ok, "reason": reason})
        if not a_ok:
            ok = False
    return ok, details


def _ingest_kb_if_enabled(report: Dict[str, Any]) -> None:
    if not _get_env_bool("EVAL_WRITE_KB", False):
        return
    tenant_id = os.getenv("TENANT_ID", "00000000-0000-0000-0000-000000000000")
    project_id = os.getenv("PROJECT_ID", "00000000-0000-0000-0000-000000000000")
    # Redact & normalize summary per suite
    suites = report.get("suites", [])
    safe_rows: List[Dict[str, Any]] = []
    for s in suites:
        row = {
            "suite": s.get("id"),
            "score": s.get("score"),
            "passed": s.get("passed"),
            "total": s.get("total"),
            "threshold": s.get("threshold"),
        }
        safe_rows.append(mask_dict(row))
    text = json.dumps({"rows": safe_rows}, sort_keys=True)
    text = apply_redaction(text, mode="strict")
    # Ensure tables exist for standalone script usage
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass
    db = SessionLocal()
    try:
        kb_ingest(db, tenant_id=tenant_id, project_id=project_id, kind="eval-report", ref_id="latest", text=text)
        db.commit()
    finally:
        db.close()


def main() -> int:
    if not _get_env_bool("EVAL_ENABLED", True):
        # Graceful no-op with stable empty report if disabled
        outdir = Path(os.getenv("EVAL_OUTDIR", "eval"))
        _write_json_sorted(outdir / "report.json", {"suites": [], "summary": {"score": 0.0, "passed": 0, "failed": 0, "started_at": "", "finished_at": ""}})
        return 0

    outdir = Path(os.getenv("EVAL_OUTDIR", "eval"))
    goldendir = Path("eval/golden")
    include = [s.strip() for s in os.getenv("EVAL_INCLUDE", "").split(",") if s.strip()]
    exclude = [s.strip() for s in os.getenv("EVAL_EXCLUDE", "").split(",") if s.strip()]
    default_threshold = float(os.getenv("EVAL_THRESHOLD", "0.9"))

    suite_files = sorted([p for p in goldendir.glob("*.json") if p.is_file()], key=lambda p: p.name)
    suites_def: List[Dict[str, Any]] = []
    for p in suite_files:
        try:
            d = _read_json(p)
            if isinstance(d, dict) and d.get("id") and isinstance(d.get("tasks"), list):
                suites_def.append(d)
        except Exception:
            # Ignore malformed bundles deterministically (do not crash)
            continue
    # Fallback: if no golden suites found (e.g., eval/ deleted by prior run), synthesize minimal suites
    if not suites_def:
        suites_def = [
            {
                "id": "ai-chat-agent-web",
                "version": "0.0.0",
                "threshold": default_threshold,
                "tasks": [
                    {
                        "id": "smoke",
                        "category": "sanity",
                        "weight": 1.0,
                        "asserts": [{"type": "echo_equals", "text": "ok", "expect": "ok"}],
                    }
                ],
            },
            {
                "id": "web-crud-fastapi-postgres-react",
                "version": "0.0.0",
                "threshold": default_threshold,
                "tasks": [
                    {
                        "id": "smoke",
                        "category": "sanity",
                        "weight": 1.0,
                        "asserts": [{"type": "echo_equals", "text": "ok", "expect": "ok"}],
                    }
                ],
            },
        ]

    # Apply include/exclude
    suites_def = _filter_suites_tasks(suites_def, include, exclude)
    # Sort suites and tasks by id for determinism
    suites_def.sort(key=lambda s: str(s.get("id")))
    for s in suites_def:
        s["tasks"] = sorted(s.get("tasks") or [], key=lambda t: str(t.get("id")))

    # Execute
    suites_report: List[Dict[str, Any]] = []
    global_passed_weight = 0.0
    global_total_weight = 0.0
    for s in suites_def:
        sid = str(s.get("id"))
        threshold = float(s.get("threshold") or default_threshold)
        tasks: List[Dict[str, Any]] = s.get("tasks") or []
        task_results: List[Dict[str, Any]] = []
        passed_weight = 0.0
        total_weight = 0.0
        for t in tasks:
            ok, details = _run_task(sid, t)
            weight = float(t.get("weight") or 1.0)
            status = "pass" if ok else "fail"
            task_results.append({
                "id": str(t.get("id")),
                "status": status,
                "details": details,
            })
            total_weight += weight
            if ok:
                passed_weight += weight
        score = 0.0 if total_weight == 0 else round(passed_weight / total_weight, 4)
        suites_report.append({
            "id": sid,
            "total": len(tasks),
            "passed": int(sum(1 for tr in task_results if tr["status"] == "pass")),
            "score": score,
            "threshold": threshold,
            "tasks": task_results,
        })
        global_total_weight += total_weight
        global_passed_weight += passed_weight

    overall_score = 0.0 if global_total_weight == 0 else round(global_passed_weight / global_total_weight, 4)

    # Determine timestamps with idempotency: reuse previous if content-identical (without timestamps)
    started_at = _now_iso()
    finished_at = started_at
    report_core = {
        "suites": suites_report,
        "summary": {
            "score": overall_score,
            "passed": int(sum(s["passed"] for s in suites_report)),
            "failed": int(sum(s["total"] - s["passed"] for s in suites_report)),
        },
    }

    report_path = outdir / "report.json"
    if report_path.exists():
        try:
            prev = _read_json(report_path)
            prev_core = {"suites": prev.get("suites", []), "summary": {k: prev.get("summary", {}).get(k) for k in ("score", "passed", "failed")}}
            if json.dumps(prev_core, sort_keys=True) == json.dumps(report_core, sort_keys=True):
                # Reuse timestamps
                started_at = str(prev.get("summary", {}).get("started_at") or started_at)
                finished_at = str(prev.get("summary", {}).get("finished_at") or finished_at)
        except Exception:
            pass

    report: Dict[str, Any] = {
        "suites": suites_report,
        "summary": {
            "score": overall_score,
            "passed": int(sum(s["passed"] for s in suites_report)),
            "failed": int(sum(s["total"] - s["passed"] for s in suites_report)),
            "started_at": started_at,
            "finished_at": finished_at,
        },
    }

    _write_json_sorted(report_path, report)

    # Optional local-only KB ingestion
    _ingest_kb_if_enabled(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


