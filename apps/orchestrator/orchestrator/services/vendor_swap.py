from __future__ import annotations

import os
import json
from typing import Any, Dict

from ..providers.registry import registry
from ..providers.shadow import ShadowManager


def _write_json_sorted(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    content = json.dumps(data, sort_keys=True) + "\n"
    cur = None
    try:
        with open(path, "r", encoding="utf-8") as f:
            cur = f.read()
    except Exception:
        cur = None
    if content != cur:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


class VendorSwapService:
    """
    Phase 61 — Auto‑Vendor Swap via Shadow→Ramp pipeline using existing PAL.
    """

    def start_shadow(self, capability: str, candidate: str) -> Dict[str, Any]:
        mgr = ShadowManager()
        return mgr.start(capability, candidate, 60)

    def run_compare_once(self, capability: str) -> Dict[str, Any]:
        mgr = ShadowManager()
        # Use conformance pattern: simulate a single op for compare
        if capability == "ads":
            return mgr.dual_write_compare("ads", {"budget_cents": 1000, "geo": "US"})
        return {"skipped": True}

    def ramp(self, capability: str, candidate: str, stage: int) -> Dict[str, Any]:
        mgr = ShadowManager()
        return mgr.ramp(capability, candidate, stage)

    def report(self, capability: str, candidate: str, *, mismatches: int) -> Dict[str, Any]:
        data = {
            "capability": capability,
            "candidate": candidate,
            "mismatches": int(mismatches),
            "policy": {"max_mismatches": 0},
            "decision": "proceed" if int(mismatches) == 0 else "hold",
        }
        out_path = os.path.join("apps", "orchestrator", "orchestrator", "self", "vendor_shadow_report.json")
        _write_json_sorted(out_path, data)
        data["artifact_path"] = out_path
        return data


