#!/usr/bin/env python3
import os
import sys
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_sorted(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, sort_keys=True) + "\n", encoding="utf-8")


def _fingerprint(report: Dict[str, Any]) -> str:
    core = {"suites": report.get("suites", []), "summary": {k: report.get("summary", {}).get(k) for k in ("score", "passed", "failed")}}
    b = json.dumps(core, sort_keys=True).encode("utf-8")
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    outdir = Path(os.getenv("EVAL_OUTDIR", "eval"))
    report_path = outdir / "report.json"
    history_path = outdir / "history.json"
    if not report_path.exists():
        # Nothing to do
        _write_json_sorted(history_path, {"runs": []})
        return 0
    report = _read_json(report_path)
    fp = _fingerprint(report)
    started = str(report.get("summary", {}).get("started_at") or "")
    finished = str(report.get("summary", {}).get("finished_at") or "")
    suites = report.get("suites", [])
    # Normalize suites view for history
    suites_min = [
        {
            "id": s.get("id"),
            "score": s.get("score"),
            "threshold": s.get("threshold"),
            "total": s.get("total"),
            "passed": s.get("passed"),
        }
        for s in suites
    ]

    rec = {
        "fingerprint": fp,
        "started_at": started,
        "finished_at": finished,
        "summary_score": report.get("summary", {}).get("score"),
        "suites": suites_min,
    }

    history: Dict[str, Any] = {"runs": []}
    if history_path.exists():
        try:
            history = _read_json(history_path)
        except Exception:
            pass
    runs: List[Dict[str, Any]] = list(history.get("runs", []))
    # De-dupe by fingerprint; if exists, update timestamps (idempotent)
    existing = None
    for r in runs:
        if r.get("fingerprint") == fp:
            existing = r
            break
    if existing is None:
        runs.append(rec)
    else:
        existing["started_at"] = rec["started_at"] or existing.get("started_at")
        existing["finished_at"] = rec["finished_at"] or existing.get("finished_at")
        existing["summary_score"] = rec["summary_score"]
        existing["suites"] = suites_min

    # Stable ordering: by finished_at then suite id inside each record
    for r in runs:
        r["suites"] = sorted(r.get("suites", []), key=lambda s: str(s.get("id")))
    runs.sort(key=lambda r: (str(r.get("finished_at")), str(r.get("fingerprint"))))

    _write_json_sorted(history_path, {"runs": runs})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


