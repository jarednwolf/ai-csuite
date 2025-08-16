#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


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


def _discover_modules(modules_dir: Path) -> Dict[str, Dict[str, Any]]:
    mods: Dict[str, Dict[str, Any]] = {}
    if not modules_dir.exists():
        return mods
    for p in sorted(modules_dir.glob("*.json"), key=lambda x: x.name):
        try:
            d = _read_json(p)
            mid = str(d.get("id") or p.stem)
            mods[mid] = d
        except Exception:
            continue
    return mods


def _load_env_manifest(env_dir: Path, env_id: str) -> Dict[str, Any]:
    path = env_dir / f"{env_id}.json"
    if not path.exists():
        raise SystemExit(f"environment manifest not found: {path}")
    try:
        d = _read_json(path)
        if not isinstance(d, dict) or not d.get("id"):
            raise ValueError("invalid environment manifest")
        return d
    except Exception as e:
        raise SystemExit(f"failed to read env manifest: {path}: {e}")


def _merge_plan(env: Dict[str, Any], all_mods: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    env_id = str(env.get("id"))
    merged_modules: List[Dict[str, Any]] = []
    pins: List[Tuple[str, str]] = []

    refs = env.get("modules") or []
    # Deterministic ordering by ref id
    refs_sorted = sorted(refs, key=lambda r: str(r.get("ref")))

    for ref in refs_sorted:
        mid = str(ref.get("ref"))
        scale: Dict[str, int] = dict(ref.get("scale") or {})
        mod = all_mods.get(mid) or {}
        resources: List[Dict[str, Any]] = []
        items = mod.get("modules") or []
        # Deterministic ordering by resource id
        items_sorted = sorted(items, key=lambda it: str(it.get("id")))
        for it in items_sorted:
            rid = str(it.get("id"))
            base = {
                "id": rid,
                "count": int(scale.get(rid, int(it.get("instances") or 1))),
            }
            # Carry version/image/engine when present
            if "version" in it:
                base["version"] = str(it.get("version"))
                pins.append((rid, str(it.get("version"))))
            if "image" in it:
                base["image"] = str(it.get("image"))
            if "engine" in it:
                base["engine"] = str(it.get("engine"))
            resources.append(base)
        merged_modules.append({"id": mid, "resources": resources})

    # Aggregate pins and sort
    pins_sorted = sorted({pid: ver for pid, ver in pins}.items(), key=lambda kv: kv[0])
    version_pins = [{"id": k, "version": v} for k, v in pins_sorted]

    plan = {
        "env": {"id": env_id, "target": str(env.get("target") or env_id)},
        "modules": sorted(merged_modules, key=lambda m: str(m.get("id"))),
        "version_pins": version_pins,
    }
    return plan


def main() -> int:
    if not _get_env_bool("IAC_ENABLED", True):
        # Graceful no-op
        return 0

    outdir = Path(_env_str("IAC_OUTDIR", "iac"))
    modules_dir = Path("iac") / "modules"
    env_dir = Path("iac") / "environments"
    env_id = _env_str("IAC_ENV", "staging")

    mods = _discover_modules(modules_dir)
    env = _load_env_manifest(env_dir, env_id)
    plan = _merge_plan(env, mods)

    _write_json_sorted(outdir / "plan.json", plan)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
