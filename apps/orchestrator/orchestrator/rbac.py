from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class Role:
    name: str
    scopes: List[str]


_ROLES: Dict[str, Role] = {
    "viewer": Role("viewer", [
        "read:planning", "read:billing", "read:enterprise", "read:cockpit",
    ]),
    "editor": Role("editor", [
        "read:planning", "write:planning",
        "read:billing", "write:billing",
        "read:enterprise",
        "read:cockpit", "write:cockpit",
    ]),
    "admin": Role("admin", [
        "read:planning", "write:planning",
        "read:billing", "write:billing",
        "read:enterprise", "write:enterprise",
        "read:cockpit", "write:cockpit",
    ]),
}


def scopes_for_role(role: str) -> List[str]:
    r = _ROLES.get((role or "").lower().strip())
    if not r:
        return _ROLES["viewer"].scopes
    return list(r.scopes)


def require_scope(scopes: List[str], required: str) -> bool:
    return required in set(scopes)


