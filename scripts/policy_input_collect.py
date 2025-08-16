#!/usr/bin/env python3
"""
Collect deterministic, local-only project facts for Phase 22 Policy-as-Code.

Inputs (local only; no network):
- sbom/licenses.json (Phase 21)
- Budget snapshot (Phase 19) via a minimal, optional read path
- Required statuses (deterministic fixtures or env-provided set)
- DoR/DoD presence via minimal local checks (artifacts presence flags)

Behavior:
- By default, emits policy/facts.json in deterministic, sorted, newline-terminated format
- Accepts --facts <path> to normalize an existing facts fixture (no external reads)
- Idempotent: re-running with same inputs produces identical output

Env:
- POLICY_INPUT: optional path to a facts fixture (same as --facts)

Output:
- policy/facts.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "policy"
OUTPUT_PATH = OUTPUT_DIR / "facts.json"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None


def _licenses_facts() -> Dict[str, Any]:
    # Phase 21 artifact
    lic_path = REPO_ROOT / "sbom/licenses.json"
    data = _read_json(lic_path) or {}
    allow = set((data.get("allowlist") or []))
    packages: List[Dict[str, Any]] = list(data.get("packages") or [])
    violations: List[str] = []
    for p in packages:
        lic = (p.get("license") or "").strip()
        classifiers: List[str] = p.get("classifiers") or []
        # Normalize basic licenses as in license_check
        norm = None
        l = lic.lower()
        if l:
            if "mit" in l:
                norm = "MIT"
            elif "apache" in l:
                norm = "Apache-2.0"
            elif "bsd" in l:
                norm = "BSD-3-Clause"
            elif "isc" in l:
                norm = "ISC"
            elif "mozilla" in l or "mpl" in l:
                norm = "MPL-2.0"
            elif "python software foundation" in l or l == "psf":
                norm = "PSF"
            elif "lgpl" in l:
                norm = "LGPL-3.0-or-later"
        if not norm and classifiers:
            # Accept classifier-derived IDs when present
            known = {"MIT","Apache-2.0","BSD-2-Clause","BSD-3-Clause","ISC","PSF","MPL-2.0","LGPL-3.0-or-later","LGPL-2.1-or-later"}
            for c in classifiers:
                if c in known:
                    norm = c
                    break
        if not norm or (allow and norm not in allow):
            if not norm:
                violations.append(f"{p.get('name','')}=={p.get('version','')} has unknown license")
            else:
                violations.append(f"{p.get('name','')}=={p.get('version','')} uses disallowed license: {norm}")
    violations.sort()
    return {
        "source": str(lic_path.relative_to(REPO_ROOT)),
        "allowlist_size": len(allow),
        "packages_count": len(packages),
        "violations": violations,
        "violations_count": len(violations),
    }


def _budget_facts() -> Dict[str, Any]:
    # Minimal local read path for tests. Prefer Phase 19 summary if present in KB/DB is not available.
    # For deterministic local-only policy, we rely on an optional file snapshot at policy/budget_snapshot.json if exists.
    snap_path = REPO_ROOT / "policy/budget_snapshot.json"
    snap = _read_json(snap_path) or {}
    status = str(snap.get("status") or snap.get("totals", {}).get("status") or "unknown")
    totals = snap.get("totals") or {}
    pct_used = float(totals.get("pct_used") or 0.0)
    return {
        "source": str(snap_path.relative_to(REPO_ROOT)) if snap else "inline",
        "status": status,
        "pct_used": round(pct_used, 4),
    }


def _statuses_facts() -> Dict[str, Any]:
    # Deterministic, local-only: allow env or file fixture
    # File form: policy/statuses.json {"statuses": [{"context":"ai-csuite/dor","state":"success"}, ...]}
    path = REPO_ROOT / "policy/statuses.json"
    data = _read_json(path) or {}
    rows: List[Dict[str, str]] = list(data.get("statuses") or [])
    ok = sorted([r.get("context") for r in rows if r.get("state") == "success" and r.get("context")])
    return {
        "source": str(path.relative_to(REPO_ROOT)) if data else "inline",
        "ok_contexts": ok,
    }


def _dor_facts() -> Dict[str, Any]:
    # Minimal presence check via a simple local manifest file to avoid DB/network
    # policy/dor.json: {"prd": true, "design": true, "research": true, "acceptance_criteria": true}
    path = REPO_ROOT / "policy/dor.json"
    data = _read_json(path) or {}
    prd = bool(data.get("prd", False))
    design = bool(data.get("design", False))
    research = bool(data.get("research", False))
    ac = bool(data.get("acceptance_criteria", False))
    ready = prd and design and research and ac
    missing: List[str] = []
    if not prd:
        missing.append("prd")
    if not design:
        missing.append("design")
    if not research:
        missing.append("research")
    if not ac:
        missing.append("prd.acceptance_criteria")
    return {
        "source": str(path.relative_to(REPO_ROOT)) if data else "inline",
        "ready": ready,
        "missing": missing,
    }


def normalize_facts(raw: Dict[str, Any]) -> Dict[str, Any]:
    # Ensure deterministic ordering and minimal keys
    return {
        "statuses": {
            "ok_contexts": sorted(list(set(raw.get("statuses", {}).get("ok_contexts", []))))
        },
        "licenses": {
            "violations": sorted(list(raw.get("licenses", {}).get("violations", []))),
            "violations_count": int(raw.get("licenses", {}).get("violations_count", 0))
        },
        "budget": {
            "status": str(raw.get("budget", {}).get("status", "unknown")),
            "pct_used": float(raw.get("budget", {}).get("pct_used", 0.0))
        },
        "dor": {
            "ready": bool(raw.get("dor", {}).get("ready", False)),
            "missing": sorted(list(raw.get("dor", {}).get("missing", [])))
        }
    }


def collect() -> Dict[str, Any]:
    # Assemble facts from local artifacts
    facts = {
        "statuses": _statuses_facts(),
        "licenses": _licenses_facts(),
        "budget": _budget_facts(),
        "dor": _dor_facts(),
    }
    return normalize_facts(facts)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Collect local policy facts")
    parser.add_argument("--facts", dest="facts_path", help="Fixture facts JSON to normalize instead of collecting", default=os.environ.get("POLICY_INPUT", ""))
    args = parser.parse_args(argv)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.facts_path:
        path = Path(args.facts_path)
        try:
            data = json.loads(path.read_text())
        except Exception as e:
            print(f"failed to read fixture facts: {e}", file=sys.stderr)
            return 2
        facts = normalize_facts(data)
    else:
        facts = collect()

    content = json.dumps(facts, sort_keys=True, indent=2) + "\n"
    if OUTPUT_PATH.exists():
        cur = OUTPUT_PATH.read_text()
        if cur != content:
            OUTPUT_PATH.write_text(content)
    else:
        OUTPUT_PATH.write_text(content)
    print(str(OUTPUT_PATH.relative_to(REPO_ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


