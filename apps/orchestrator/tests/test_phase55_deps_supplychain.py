import json
import os
from pathlib import Path

from orchestrator.supply_chain.upgrader import scan_and_propose, apply_proposal


def test_supply_chain_upgrader_proposes_and_applies_minor_bumps(tmp_path):
    # Prepare a copy of lockfile in place (tests run in repo root)
    lock_path = Path("apps/orchestrator/requirements.lock.txt")
    assert lock_path.exists(), "baseline lockfile missing"

    # Run scan (offline; deterministic)
    prop = scan_and_propose()
    assert isinstance(prop.updates, dict)
    assert prop.rationale
    assert prop.risk in {"low", "medium", "high"}

    # Apply proposal (idempotent write, sorted)
    out = apply_proposal(prop)
    assert set(out.keys()) == {"updated", "changelog", "risk"}
    text = lock_path.read_text(encoding="utf-8")
    lines = [l for l in text.splitlines() if l.strip()]
    assert lines == sorted(lines)
    assert text.endswith("\n")

    # Proposal report persisted
    rep_path = Path("apps/orchestrator/orchestrator/reports/supply_chain/proposal.json")
    assert rep_path.exists()
    data = json.loads(rep_path.read_text(encoding="utf-8"))
    assert data["risk"] == out["risk"]
    assert data["changelog"] == out["changelog"]


