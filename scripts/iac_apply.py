#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_sorted(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, sort_keys=True) + "\n", encoding="utf-8")


def _env_str(name: str, default: str) -> str:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip() or default


def _flatten_resources(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for m in sorted(plan.get("modules") or [], key=lambda z: str(z.get("id"))):
        for r in sorted(m.get("resources") or [], key=lambda z: str(z.get("id"))):
            base = {"id": str(r.get("id")), "count": int(r.get("count") or 0)}
            if "version" in r:
                base["version"] = str(r.get("version"))
            if "image" in r:
                base["image"] = str(r.get("image"))
            if "engine" in r:
                base["engine"] = str(r.get("engine"))
            out.append(base)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Local IaC apply simulator")
    parser.add_argument("--destroy", action="store_true", help="simulate teardown deterministically")
    args = parser.parse_args()

    outdir = Path(_env_str("IAC_OUTDIR", "iac"))
    plan_path = outdir / "plan.json"
    if not plan_path.exists():
        raise SystemExit(f"plan file not found: {plan_path}")

    plan = _read_json(plan_path)
    env = plan.get("env") or {}
    pins = plan.get("version_pins") or []

    if args.destroy:
        state = {"env": env, "resources": [], "status": "destroyed", "version_pins": pins}
    else:
        resources = _flatten_resources(plan)
        state = {"env": env, "resources": resources, "status": "applied", "version_pins": pins}

    _write_json_sorted(outdir / "state.json", state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
