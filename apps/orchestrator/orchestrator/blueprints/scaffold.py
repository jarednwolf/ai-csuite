from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict

from ..blueprints.registry import registry


def _write_text_if_changed(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cur = None
    try:
        with open(path, "r", encoding="utf-8") as f:
            cur = f.read()
    except Exception:
        cur = None
    if cur != text:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


def scaffold_from_blueprint(*, blueprint_id: str) -> Dict[str, Any]:
    # Validate exists via registry
    bp = registry().get(blueprint_id)
    op_id = str(uuid.uuid4())
    out = {
        "op_id": op_id,
        "blueprint_id": bp.id,
        "generated": [
            {"path": f"apps/{bp.id}/README.md", "status": "planned"},
            {"path": f"apps/{bp.id}/tests/test_smoke.py", "status": "planned"},
        ],
    }
    # Persist minimal report and rely on Phase 26 validator already
    path = os.path.join("blueprints", "report.json")
    try:
        report = {"blueprints": [], "summary": {"started_at": "", "finished_at": ""}}
        _write_text_if_changed(path, json.dumps(report, sort_keys=True) + "\n")
    except Exception:
        pass
    return out



