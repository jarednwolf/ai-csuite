from __future__ import annotations

from typing import Dict


def validate_config(protocol: str, config: Dict) -> Dict:
    p = (protocol or "").lower().strip()
    if p not in {"oidc", "saml"}:
        return {"ok": False, "error": "unsupported protocol"}
    cfg = dict(config or {})
    # Deterministic minimal shape requirements
    if p == "oidc":
        required = ["issuer", "client_id", "client_secret"]
    else:
        required = ["idp_entity_id", "sso_url", "certificate"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        return {"ok": False, "error": "missing", "fields": sorted(missing)}
    return {"ok": True, "normalized": {k: cfg[k] for k in required}}


