from __future__ import annotations

from typing import Dict, Any, List


def run_agent_review(*, diff_summary: str, links: List[str]) -> Dict[str, Any]:
    """
    Deterministic cross-agent review skeleton.
    Produces ADR-like structure with Steelman, Options, Decision, Owner.
    Offline/no network.
    """
    steelman = {
        "problem": diff_summary,
        "risks": ["scope creep", "docs drift"],
        "invariants": ["deterministic tests", "policy compliance"],
    }
    options = [
        {"id": "A", "desc": "Proceed with docs-only PR", "tradeoffs": ["low risk", "limited impact"]},
        {"id": "B", "desc": "Block pending ADR edits", "tradeoffs": ["safer", "slower feedback"]},
    ]
    decision = {"chosen": "A", "rationale": "low risk and aligns with self-docs policy"}
    owner = {"role": "CTO", "status_context": "ai-csuite/self-review"}
    return {
        "version": 1,
        "links": list(links or []),
        "steelman": steelman,
        "options": options,
        "decision": decision,
        "owner": owner,
    }


