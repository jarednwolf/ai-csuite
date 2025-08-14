import os, hmac, hashlib
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from .db import get_db
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
            repo = payload["repository"]["name"]
            owner = payload["repository"]["owner"]["login"]
            branch = payload["pull_request"]["head"]["ref"]
            number = payload["number"]
            res = ensure_and_update_for_branch_event(db, owner, repo, branch, number)
            return {"ok": True, "handled": True, "result": res}
        return {"ok": True, "handled": False, "reason": f"action {action} ignored"}
    return {"ok": True, "handled": False, "reason": f"event {event} ignored"}


