from __future__ import annotations

import json, time, uuid
from typing import Any, Dict, Mapping, Optional, Tuple

from .registry import registry


_SHADOW_STATE: Dict[str, Mapping[str, Any]] = {}
_RAMP_STATE: Dict[str, int] = {}


class ShadowManager:
    def __init__(self) -> None:
        self._registry = registry()

    def start(self, capability: str, candidate: str, duration_sec: int = 120) -> Mapping[str, Any]:
        sid = str(uuid.uuid4())
        _SHADOW_STATE[sid] = {
            "capability": capability,
            "candidate": candidate,
            "active": True,
            "ends_at": time.time() + max(1, int(duration_sec)),
            "diff": {"fields_mismatch": 0, "errors": 0},
        }
        return {"shadow_id": sid}

    def stop(self, shadow_id: str) -> Mapping[str, Any]:
        st = _SHADOW_STATE.get(shadow_id)
        if not st:
            return {"stopped": False, "reason": "not_found"}
        st = dict(st)
        st["active"] = False
        _SHADOW_STATE[shadow_id] = st
        return {"stopped": True}

    def dual_write_compare(self, capability: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        # Exercise two adapters: active and candidate (if any active shadow exists for cap)
        active_name = self._registry._active.get(capability)
        if not active_name:
            return {"skipped": True}
        active = self._registry.get(capability)
        # Find any active shadow for this capability
        cand_name = None
        shadow_id = None
        for sid, st in _SHADOW_STATE.items():
            if st.get("capability") == capability and st.get("active"):
                cand_name = st.get("candidate")
                shadow_id = sid
                break
        if not cand_name:
            # no shadow
            return {"skipped": True}
        candidate = self._registry._build(capability, cand_name)
        # For demonstration, only support ads.create_campaign compare
        a = active.create_campaign(payload)
        b = candidate.create_campaign(payload)
        # Simple diff: count differing keys/values
        mismatches = 0
        for k in sorted(set(list(a.keys()) + list(b.keys()))):
            if a.get(k) != b.get(k):
                mismatches += 1
        if shadow_id:
            st = dict(_SHADOW_STATE.get(shadow_id) or {})
            diff = dict(st.get("diff") or {})
            diff["fields_mismatch"] = int(diff.get("fields_mismatch", 0)) + mismatches
            st["diff"] = diff
            _SHADOW_STATE[shadow_id] = st
        return {"mismatches": mismatches, "shadow_id": shadow_id, "candidate": cand_name}

    def ramp(self, capability: str, candidate: str, stage: int) -> Mapping[str, Any]:
        # stage in {5,25,50,100}
        _RAMP_STATE[f"{capability}:{candidate}"] = int(stage)
        # Promote when 100
        if stage == 100:
            self._registry.set_override(capability, candidate)
            # Mark any matching shadow ended
            for sid, st in list(_SHADOW_STATE.items()):
                if st.get("capability") == capability and st.get("candidate") == candidate:
                    _SHADOW_STATE[sid] = dict(st, active=False)
        return {"capability": capability, "candidate": candidate, "stage": int(stage)}

    def ramp_stage(self, capability: str, candidate: str) -> int:
        return int(_RAMP_STATE.get(f"{capability}:{candidate}", 0))


