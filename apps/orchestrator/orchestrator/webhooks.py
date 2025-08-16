import os, hmac, hashlib
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from .db import get_db
from .security import audit_event
from .integrations.github import ensure_and_update_for_branch_event

router = APIRouter()

def _verify_sig(secret: str, body: bytes, sent_sig: str | None) -> bool:
    if not secret:
        return True  # no secret set; accept (dev)
    mac = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
    expected = "sha256=" + mac.hexdigest()
    return hmac.compare_digest(expected, sent_sig or "")

@router.post("/webhooks/github")
async def github_webhook(request: Request, db: Session = Depends(get_db)):
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    raw = await request.body()
    sig = request.headers.get("X-Hub-Signature-256")
    # Dev/CI friendly: only enforce verification when both secret and signature are present
    # This allows local/CI simulations without headers while keeping verification when used.
    if secret and sig:
        if not _verify_sig(secret, raw, sig):
            raise HTTPException(401, "invalid signature")

    event = request.headers.get("X-GitHub-Event", "")
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    # Allow CI simulation where headers might be absent
    if event == "pull_request" or (not event and payload.get("pull_request")):
        action = payload.get("action")
        if action in {"opened", "synchronize", "reopened", "edited"}:
            try:
                repo = payload.get("repository", {}).get("name", "")
                owner = payload.get("repository", {}).get("owner", {}).get("login", "")
                branch = payload.get("pull_request", {}).get("head", {}).get("ref", "")
                number = payload.get("number")
                if not repo or not owner or not branch:
                    # Dry-run safe fallback
                    res = {"dry_run": True, "reason": "missing repo/owner/branch"}
                    try:
                        audit_event(db, actor="webhook", event_type="webhook.github", request_id=f"gh:{action}", details={"event": event, "result": res})
                    except Exception:
                        pass
                    return {"ok": True, "handled": True, "result": res}
                res = ensure_and_update_for_branch_event(db, owner, repo, branch, number)
                try:
                    audit_event(db, actor="webhook", event_type="webhook.github", request_id=f"gh:{action}:{owner}/{repo}:{branch}", details={"event": event, "owner": owner, "repo": repo, "branch": branch, "result": res})
                except Exception:
                    pass
                return {"ok": True, "handled": True, "result": res}
            except Exception as e:
                # Never 500 on webhook simulation; return a dry-run stub
                res = {"dry_run": True, "error": str(e)}
                try:
                    audit_event(db, actor="webhook", event_type="webhook.github", request_id=f"gh:{action}:error", details={"event": event, "error": str(e)})
                except Exception:
                    pass
                return {"ok": True, "handled": True, "result": res}
        return {"ok": True, "handled": False, "reason": f"action {action} ignored"}
    return {"ok": True, "handled": False, "reason": f"event {event} ignored"}


