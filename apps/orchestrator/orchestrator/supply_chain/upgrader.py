from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class Proposal:
    updates: Dict[str, str]
    rationale: str
    risk: str


def _read_lines(path: str) -> List[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [l.rstrip("\n") for l in f.readlines()]
    except Exception:
        return []


def _write_text_if_changed(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    prior = None
    try:
        with open(path, "r", encoding="utf-8") as f:
            prior = f.read()
    except Exception:
        prior = None
    if prior != text:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


def _load_catalog() -> Dict[str, str]:
    # Deterministic offline catalog for suggested bumps
    here = os.path.dirname(__file__)
    catalog_path = os.path.join(here, "fixtures", "version_catalog.json")
    try:
        with open(catalog_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _normalize_req_line(line: str) -> Tuple[str, str] | None:
    m = re.match(r"^([a-zA-Z0-9_.\-]+)==([^\s#]+)$", line.strip())
    if not m:
        return None
    return m.group(1).lower(), m.group(2)


def scan_and_propose() -> Proposal:
    # Inputs: orchestrator lockfile only (others identical style)
    lock_path = os.path.join("apps", "orchestrator", "requirements.lock.txt")
    lines = [l for l in _read_lines(lock_path) if l.strip()]
    catalog = _load_catalog()
    updates: Dict[str, str] = {}
    for l in lines:
        nv = _normalize_req_line(l)
        if not nv:
            continue
        name, ver = nv
        target = catalog.get(name)
        if target and target != ver:
            # Only allow minor/patch bumps: same major
            def major(v: str) -> str:
                try:
                    return v.split(".")[0]
                except Exception:
                    return v
            if major(target) == major(ver):
                updates[name] = target
    rationale = "Minor/patch bumps proposed from offline catalog to reduce risk (no majors)."
    risk = "low"
    return Proposal(updates=updates, rationale=rationale, risk=risk)


def apply_proposal(p: Proposal) -> Dict[str, str]:
    lock_path = os.path.join("apps", "orchestrator", "requirements.lock.txt")
    lines = _read_lines(lock_path)
    new_lines: List[str] = []
    for raw in lines:
        nv = _normalize_req_line(raw)
        if not nv:
            if raw.strip():
                new_lines.append(raw.strip())
            continue
        name, ver = nv
        if name in p.updates:
            new_lines.append(f"{name}=={p.updates[name]}")
        else:
            new_lines.append(f"{name}=={ver}")
    new_lines = [l for l in new_lines if l]
    new_lines_sorted = sorted(new_lines)
    content = "\n".join(new_lines_sorted) + "\n"
    _write_text_if_changed(lock_path, content)
    # Write SBOM and license reports via existing scripts (invoked by tests separately)
    out = {
        "updated": sorted(list(p.updates.keys())),
        "changelog": p.rationale,
        "risk": p.risk,
    }
    report_path = os.path.join("apps", "orchestrator", "orchestrator", "reports", "supply_chain", "proposal.json")
    _write_text_if_changed(report_path, json.dumps(out, sort_keys=True) + "\n")
    return out



