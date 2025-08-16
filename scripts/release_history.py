#!/usr/bin/env python3
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
    core = {
        "env": (report.get("env") or {}).get("id"),
        "steps": [
            {
                "percent": int(s.get("percent")),
                "metrics": {
                    "error_rate": float((s.get("metrics") or {}).get("error_rate") or 0.0),
                    "p95_ms": int((s.get("metrics") or {}).get("p95_ms") or 0),
                },
            }
            for s in (report.get("steps") or [])
        ],
        "threshold_err": (report.get("summary") or {}).get("threshold_err"),
        "threshold_p95": (report.get("summary") or {}).get("threshold_p95"),
    }
    b = json.dumps(core, sort_keys=True).encode("utf-8")
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    deploy_dir = Path("deployments")
    report_path = deploy_dir / "report.json"
    history_path = deploy_dir / "history.json"

    if not report_path.exists():
        # Create empty history deterministically
        _write_json_sorted(history_path, {"runs": []})
        return 0

    report = _read_json(report_path)
    fp = _fingerprint(report)
    summary = report.get("summary") or {}
    env = report.get("env") or {}
    entry = {
        "env": env.get("id"),
        "failed": int(summary.get("failed") or 0),
        "finished_at": str(summary.get("finished_at") or ""),
        "id": fp,
        "passed": int(summary.get("passed") or 0),
        "score": float(summary.get("score") or 0.0),
        "started_at": str(summary.get("started_at") or ""),
        "status": str(summary.get("status") or "pass"),
    }

    runs: List[Dict[str, Any]] = []
    if history_path.exists():
        try:
            hist = _read_json(history_path)
            existing = hist.get("runs") or []
            # Deduplicate by fingerprint
            seen = set()
            for r in existing:
                rid = str(r.get("id"))
                if rid == fp:
                    if rid not in seen:
                        runs.append(r)
                        seen.add(rid)
                else:
                    if rid not in seen:
                        runs.append(r)
                        seen.add(rid)
            if fp not in seen:
                runs.append(entry)
        except Exception:
            runs = [entry]
    else:
        runs = [entry]

    # Stable sort: by started_at then env id
    def _key(r: Dict[str, Any]) -> Any:
        return (str(r.get("started_at") or ""), str(r.get("env") or ""))

    runs.sort(key=_key)
    _write_json_sorted(history_path, {"runs": runs})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
