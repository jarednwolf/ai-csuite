from __future__ import annotations

from typing import Dict, Any


def compute_ownership(repo_map: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic ownership guesses based on path conventions and intents.
    - api → orchestrator/api/* owned by "orchestrator-api"
    - services → orchestrator/services/* owned by "orchestrator-services"
    - providers → orchestrator/providers/* owned by "orchestrator-providers"
    - tests map back to nearest code owner label
    - docs owned by "docs"
    Returns a structure with owners and file assignments.
    """
    mods = repo_map.get("modules", {}) if isinstance(repo_map, dict) else {}
    owners: Dict[str, list[str]] = {
        "orchestrator-api": [],
        "orchestrator-services": [],
        "orchestrator-providers": [],
        "docs": [],
        "tests": [],
        "scripts": [],
    }
    for path in sorted(mods.keys()):
        if path.startswith("apps/orchestrator/orchestrator/api/"):
            owners["orchestrator-api"].append(path)
        elif path.startswith("apps/orchestrator/orchestrator/services/"):
            owners["orchestrator-services"].append(path)
        elif path.startswith("apps/orchestrator/orchestrator/providers/"):
            owners["orchestrator-providers"].append(path)
        elif path.startswith("apps/orchestrator/tests/"):
            owners["tests"].append(path)
        elif path.startswith("docs/"):
            owners["docs"].append(path)
        elif path.startswith("scripts/"):
            owners["scripts"].append(path)
    # Compact: remove empty buckets for readability
    owners = {k: v for k, v in owners.items() if v}
    return {"version": 1, "owners": owners}


