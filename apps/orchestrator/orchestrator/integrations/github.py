import base64, json, os, re, uuid
from typing import Optional, Tuple, Dict, Any, List
import httpx
from sqlalchemy.orm import Session

from ..models import Project, RoadmapItem, PRD, DesignCheck, ResearchNote, RunDB, PullRequest
from ..discovery import dor_check

GITHUB_API_BASE = os.getenv("GITHUB_API_BASE", "https://api.github.com")

CTX_DOR = "ai-csuite/dor"
CTX_HUMAN = "ai-csuite/human-approval"
CTX_ARTIFACTS = "ai-csuite/artifacts"

COMMENT_MARKER_PREFIX = "ai-csuite:summary"

def _write_enabled() -> bool:
    return os.getenv("GITHUB_WRITE_ENABLED", "1").strip().lower() not in {"0", "false", "no"}

def build_pr_summary_md(*, project_name: str, item_title: str, branch: str,
                        dor_pass: bool, missing: list[str], owner: str, repo: str,
                        base_dir: str) -> str:
    ok = "✅ Pass" if dor_pass else "❌ Blocked"
    links = []
    for fname in ("prd.json", "design.md", "research.md"):
        links.append(f"- [{fname}](https://github.com/{owner}/{repo}/blob/{branch}/{base_dir}/{fname})")
    miss = "" if dor_pass else f"\n**Missing**: {', '.join(missing)}\n"
    marker = f"<!-- {COMMENT_MARKER_PREFIX}:{branch} -->"
    return f"""### AI‑CSuite Summary — {project_name} / {item_title}

**Definition of Ready:** {ok}{miss}

**Artifacts**
{chr(10).join(links)}

_Updated automatically by AI‑CSuite on branch `{branch}`._
{marker}
"""

def _list_issue_comments(client: httpx.Client, owner: str, repo: str, number: int, headers: dict) -> list[dict]:
    r = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{number}/comments", headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

def _create_issue_comment(client: httpx.Client, owner: str, repo: str, number: int, body: str, headers: dict) -> dict:
    r = client.post(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{number}/comments", headers=headers, json={"body": body}, timeout=30)
    r.raise_for_status()
    return r.json()

def _update_issue_comment(client: httpx.Client, owner: str, repo: str, comment_id: int, body: str, headers: dict) -> dict:
    r = client.patch(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/comments/{comment_id}", headers=headers, json={"body": body}, timeout=30)
    r.raise_for_status()
    return r.json()

def _find_marker_comment_id(comments: list[dict], branch: str) -> int | None:
    marker = f"{COMMENT_MARKER_PREFIX}:{branch}"
    for c in comments:
        if isinstance(c.get("body"), str) and marker in c["body"]:
            return int(c["id"])
    return None

def _slug(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "change"

def _parse_repo_url(url: str) -> Optional[Tuple[str, str]]:
    if not url:
        return None
    m = re.search(r"github\.com[:/]+([^/]+)/([^/.]+)", url)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    return owner, repo

def _b64(content: bytes) -> str:
    return base64.b64encode(content).decode("ascii")

def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

def _get_repo(client: httpx.Client, owner: str, repo: str, headers: dict):
    r = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}", headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

def _get_ref(client: httpx.Client, owner: str, repo: str, branch: str, headers: dict):
    r = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/ref/heads/{branch}", headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

def _create_branch(client: httpx.Client, owner: str, repo: str, new_branch: str, base_sha: str, headers: dict):
    body = {"ref": f"refs/heads/{new_branch}", "sha": base_sha}
    r = client.post(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/refs", headers=headers, json=body, timeout=30)
    if r.status_code in (201,):
        return r.json()
    if r.status_code == 422 and "Reference already exists" in r.text:
        return {"ref": f"refs/heads/{new_branch}"}
    r.raise_for_status()
    return r.json()

def _get_file_sha_if_exists(client: httpx.Client, owner: str, repo: str, path: str, branch: str, headers: dict) -> Optional[str]:
    r = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}", headers=headers, params={"ref": branch}, timeout=30)
    if r.status_code == 200:
        return r.json().get("sha")
    return None

def _put_file(client: httpx.Client, owner: str, repo: str, path: str, content: bytes, message: str, branch: str, headers: dict):
    sha = _get_file_sha_if_exists(client, owner, repo, path, branch, headers)
    body = {"message": message, "content": _b64(content), "branch": branch}
    if sha:
        body["sha"] = sha
    r = client.put(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}", headers=headers, json=body, timeout=30)
    r.raise_for_status()
    return r.json()

def _create_pr(client: httpx.Client, owner: str, repo: str, head: str, base: str, title: str, body: str, headers: dict):
    r = client.post(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls",
                    headers=headers,
                    json={"title": title, "head": head, "base": base, "body": body},
                    timeout=30)
    r.raise_for_status()
    return r.json()

def _set_status(client: httpx.Client, owner: str, repo: str, sha: str, *, context: str, state: str, description: str = "", target_url: Optional[str] = None, headers: dict):
    # state ∈ {"error","failure","pending","success"}
    body = {"state": state, "context": context, "description": description or ""}
    if target_url:
        body["target_url"] = target_url
    r = client.post(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/statuses/{sha}", headers=headers, json=body, timeout=30)
    r.raise_for_status()
    return r.json()

def _get_combined_status(client: httpx.Client, owner: str, repo: str, sha: str, headers: dict) -> dict:
    r = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits/{sha}/status", headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

def _merge_pr(client: httpx.Client, owner: str, repo: str, number: int, *, method: str = "squash", commit_title: Optional[str] = None, commit_message: Optional[str] = None, headers: dict = {}):
    body: Dict[str, Any] = {"merge_method": method}
    if commit_title:
        body["commit_title"] = commit_title
    if commit_message:
        body["commit_message"] = commit_message
    r = client.put(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{number}/merge", headers=headers, json=body, timeout=30)
    r.raise_for_status()
    return r.json()

def _required_contexts() -> List[str]:
    env_val = os.getenv("GITHUB_REQUIRED_CONTEXTS", "").strip()
    if not env_val:
        return [CTX_DOR, CTX_HUMAN]
    return [c.strip() for c in env_val.split(",") if c.strip()]

def verify_repo_access(repo_url: str) -> dict:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return {"ok": False, "reason": "GITHUB_TOKEN not set"}
    parsed = _parse_repo_url(repo_url)
    if not parsed:
        return {"ok": False, "reason": "Unsupported repo_url (must be GitHub)"}
    owner, repo = parsed
    with httpx.Client() as c:
        try:
            info = _get_repo(c, owner, repo, _headers(token))
            return {"ok": True, "repo": f"{owner}/{repo}", "default_branch": info.get("default_branch", "main")}
        except httpx.HTTPStatusError as e:
            return {"ok": False, "reason": f"GitHub API error: {e.response.status_code} {e.response.text[:200]}"}

def open_pr_for_run(db: Session, run_id: str) -> dict:
    """
    Creates a feature branch, commits discovery artifacts, opens a PR,
    and publishes commit statuses (DoR, human-approval pending, artifacts).
    Skips gracefully if token absent or repo_url is unsupported.
    """
    # Respect dry-run first for deterministic CI behavior
    if not _write_enabled():
        return {"skipped": "GITHUB_WRITE_ENABLED=0"}
    # Optional kill-switch for tests/CI (secondary)
    if os.getenv("GITHUB_PR_ENABLED", "1").strip().lower() in {"0", "false", "no"}:
        return {"skipped": "PR disabled by env (GITHUB_PR_ENABLED=0)"}
    token = os.getenv("GITHUB_TOKEN")
    # Only require token if we intend to write to GitHub
    if _write_enabled() and not token:
        return {"skipped": "GITHUB_TOKEN not set"}

    run = db.get(RunDB, run_id)
    if not run:
        return {"error": "run not found"}
    project = db.get(Project, run.project_id)
    item = db.get(RoadmapItem, run.roadmap_item_id) if run.roadmap_item_id else None
    if not project or not project.repo_url:
        return {"skipped": "project.repo_url not set"}
    parsed = _parse_repo_url(project.repo_url)
    if not parsed:
        return {"skipped": "non-GitHub repo_url"}
    owner, repo = parsed

    # Gather artifacts
    prd = (
        db.query(PRD)
        .filter(PRD.project_id == run.project_id, PRD.roadmap_item_id == run.roadmap_item_id)
        .order_by(PRD.created_at.desc())
        .first()
    )
    design = (
        db.query(DesignCheck)
        .filter(DesignCheck.project_id == run.project_id, DesignCheck.roadmap_item_id == run.roadmap_item_id)
        .order_by(DesignCheck.created_at.desc())
        .first()
    )
    research = (
        db.query(ResearchNote)
        .filter(ResearchNote.project_id == run.project_id, ResearchNote.roadmap_item_id == run.roadmap_item_id)
        .order_by(ResearchNote.created_at.desc())
        .first()
    )

    # DoR summary (for PR + status)
    ok, missing, _ = dor_check(db, run.tenant_id, run.project_id, run.roadmap_item_id) if run.roadmap_item_id else (True, [], {})
    item_title = (item.title if item else "Change")
    proj_name = project.name

    branch = f"feature/{(run.roadmap_item_id or run.id)[:8]}-{_slug(item_title)}"
    pr_title = f"[AI‑CSuite] {proj_name} — {item_title} (Run {run.id[:8]})"
    body_lines = [
        f"### Definition of Ready: {'✅ Pass' if ok else '❌ Blocked'}",
        ("" if ok else f"**Missing**: {', '.join(missing)}"),
        "",
        "**Artifacts:**",
        f"- PRD: {prd.id if prd else 'N/A'}",
        f"- Design: {design.id if design else 'N/A'}",
        f"- Research: {research.id if research else 'N/A'}",
        "",
        f"_Generated by AI‑CSuite · Run {run.id}_"
    ]
    pr_body = "\n".join([line for line in body_lines if line is not None])

    # Serialize artifact files
    files = []
    base_dir = f"docs/roadmap/{(run.roadmap_item_id or run.id)[:8]}-{_slug(item_title)}"
    if prd:
        files.append((f"{base_dir}/prd.json", json.dumps(prd.prd_json, indent=2).encode("utf-8")))
    if design:
        design_md = f"""# Design Heuristics Review

**Passes:** {design.passes}
**Score:** {design.heuristics_score}

_Accessibility notes:_
{design.a11y_notes}
"""
        files.append((f"{base_dir}/design.md", design_md.encode("utf-8")))
    if research:
        research_md = f"""# Research Summary

{research.summary}

## Evidence
""" + "\n".join([f"- {e}" for e in (research.evidence or [])])
        files.append((f"{base_dir}/research.md", research_md.encode("utf-8")))

    run_meta_path = f"{base_dir}/run-{run.id}.json"
    run_meta = {
        "run_id": run.id,
        "tenant_id": run.tenant_id,
        "project_id": run.project_id,
        "roadmap_item_id": run.roadmap_item_id,
        "phase": run.phase,
        "status": run.status,
    }
    files.append((run_meta_path, json.dumps(run_meta, indent=2).encode("utf-8")))

    headers = _headers(token)
    with httpx.Client() as c:
        # Repo & base branch
        repo_info = _get_repo(c, owner, repo, headers)
        base_branch = repo_info.get("default_branch", "main")
        base_ref = _get_ref(c, owner, repo, base_branch, headers)
        base_sha = base_ref["object"]["sha"]

        # Create branch (idempotent)
        _create_branch(c, owner, repo, branch, base_sha, headers)

        # Commit files (one PUT per file)
        for path, content in files:
            _put_file(c, owner, repo, path, content, f"chore(ai-csuite): add artifacts for {item_title} (run {run.id[:8]})", branch, headers)

        # Create PR (idempotent-ish)
        try:
            pr = _create_pr(c, owner, repo, head=branch, base=base_branch, title=pr_title, body=pr_body, headers=headers)
        except httpx.HTTPStatusError as e:
            r = c.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls", headers=headers, params={"state":"open","head":f"{owner}:{branch}"}, timeout=30)
            if r.status_code == 200 and r.json():
                pr = r.json()[0]
            else:
                raise

        # Get head SHA of branch
        head_ref = _get_ref(c, owner, repo, branch, headers)
        head_sha = head_ref["object"]["sha"]

        # Publish commit statuses
        _set_status(
            c, owner, repo, head_sha,
            context=CTX_DOR,
            state=("success" if ok else "failure"),
            description=("DoR passed" if ok else "DoR blocked"),
            headers=headers,
        )
        _set_status(
            c, owner, repo, head_sha,
            context=CTX_HUMAN,
            state="pending",
            description="Waiting for human approval",
            headers=headers,
        )
        _set_status(
            c, owner, repo, head_sha,
            context=CTX_ARTIFACTS,
            state="success",
            description="Artifacts committed by AI‑CSuite",
            headers=headers,
        )

        # After publishing statuses, upsert summary comment (best-effort)
        try:
            _ = upsert_pr_summary_comment_for_run(db, run.id)
        except Exception:
            pass

    # Persist PR metadata
    pr_row = PullRequest(
        id=str(uuid.uuid4()),
        run_id=run.id,
        project_id=project.id,
        repo=f"{owner}/{repo}",
        branch=branch,
        number=int(pr["number"]),
        url=pr["html_url"],
        state=pr["state"],
    )
    db.add(pr_row)
    db.commit()

    return {"created": True, "url": pr_row.url, "number": pr_row.number, "branch": pr_row.branch, "repo": pr_row.repo}

def _pr_info_for_run(db: Session, run_id: str):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return None, {"skipped": "GITHUB_TOKEN not set"}
    row = (
        db.query(PullRequest)
        .filter(PullRequest.run_id == run_id)
        .order_by(PullRequest.created_at.desc())
        .first()
    )
    if not row:
        return None, {"error": "no PR recorded for this run"}
    owner, repo = row.repo.split("/", 1)
    headers = _headers(token)
    with httpx.Client() as c:
        pr = c.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{row.number}", headers=headers, timeout=30)
        pr.raise_for_status()
        prj = pr.json()
        head_sha = prj["head"]["sha"]
        return {"owner": owner, "repo": repo, "number": row.number, "head_sha": head_sha, "branch": row.branch}, None

def set_status_for_run(db: Session, run_id: str, *, context: str, state: str, description: str = "") -> dict:
    info, err = _pr_info_for_run(db, run_id)
    if err:
        return err
    headers = _headers(os.getenv("GITHUB_TOKEN",""))
    with httpx.Client() as c:
        res = _set_status(c, info["owner"], info["repo"], info["head_sha"], context=context, state=state, description=description, headers=headers)
        return {"ok": True, "context": context, "state": state, "status_id": res.get("id")}

def approve_pr_for_run(db: Session, run_id: str) -> dict:
    return set_status_for_run(db, run_id, context=CTX_HUMAN, state="success", description="Approved by human")

def refresh_dor_status_for_run(db: Session, run_id: str) -> dict:
    run = db.get(RunDB, run_id)
    if not run:
        return {"error": "run not found"}
    ok, missing, _ = dor_check(db, run.tenant_id, run.project_id, run.roadmap_item_id) if run.roadmap_item_id else (True, [], {})
    state = "success" if ok else "failure"
    desc = "DoR passed" if ok else f"DoR blocked: {', '.join(missing)}"
    res = set_status_for_run(db, run_id, context=CTX_DOR, state=state, description=desc)
    res["dor_pass"] = ok
    if not ok:
        res["missing"] = missing
    return res

def statuses_for_run(db: Session, run_id: str) -> dict:
    info, err = _pr_info_for_run(db, run_id)
    if err:
        return err
    headers = _headers(os.getenv("GITHUB_TOKEN",""))
    with httpx.Client() as c:
        comb = _get_combined_status(c, info["owner"], info["repo"], info["head_sha"], headers)
        contexts = []
        for s in comb.get("statuses", []):
            contexts.append({
                "context": s.get("context"),
                "state": s.get("state"),
                "description": s.get("description"),
                "target_url": s.get("target_url"),
                "updated_at": s.get("updated_at"),
            })
        req = _required_contexts()
        # compute merge readiness
        state_map = {s["context"]: s["state"] for s in contexts}
        missing_ctx = [c for c in req if c not in state_map]
        not_green = [c for c in req if state_map.get(c) != "success"]
        can_merge = (len(missing_ctx) == 0 and len(not_green) == 0)
        return {
            "repo": f'{info["owner"]}/{info["repo"]}',
            "number": info["number"],
            "head_sha": info["head_sha"],
            "state": comb.get("state"),  # overall state
            "required_contexts": req,
            "statuses": contexts,
            "can_merge": can_merge,
            "missing_contexts": missing_ctx,
            "not_green": not_green,
        }

def upsert_pr_summary_comment_for_run(db: Session, run_id: str) -> dict:
    if not _write_enabled():
        return {"skipped": "GITHUB_WRITE_ENABLED=0"}

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return {"skipped": "GITHUB_TOKEN not set"}

    run = db.get(RunDB, run_id)
    if not run:
        return {"error": "run not found"}
    project = db.get(Project, run.project_id)
    item = db.get(RoadmapItem, run.roadmap_item_id) if run.roadmap_item_id else None

    # Need PR metadata to know owner/repo/branch/number
    pr = (
        db.query(PullRequest)
        .filter(PullRequest.run_id == run_id)
        .order_by(PullRequest.created_at.desc())
        .first()
    )
    if not pr:
        return {"error": "no PR recorded for this run"}
    owner, repo = pr.repo.split("/", 1)
    branch = pr.branch
    number = pr.number

    ok, missing, _ = dor_check(db, run.tenant_id, run.project_id, run.roadmap_item_id)
    base_dir = f"docs/roadmap/{(run.roadmap_item_id or run.id)[:8]}-{_slug(item.title if item else 'change')}"
    body = build_pr_summary_md(
        project_name=project.name, item_title=item.title if item else "Change",
        branch=branch, dor_pass=ok, missing=missing, owner=owner, repo=repo, base_dir=base_dir
    )

    headers = _headers(token)
    with httpx.Client() as c:
        comments = _list_issue_comments(c, owner, repo, number, headers)
        cid = _find_marker_comment_id(comments, branch)
        if cid:
            res = _update_issue_comment(c, owner, repo, cid, body, headers)
        else:
            res = _create_issue_comment(c, owner, repo, number, body, headers)
        return {"ok": True, "comment_id": res.get("id")}

def merge_pr_for_run(db: Session, run_id: str, method: str = "squash") -> dict:
    info, err = _pr_info_for_run(db, run_id)
    if err:
        return err
    # Check required statuses
    st = statuses_for_run(db, run_id)
    if not st.get("can_merge"):
        return {"blocked": True, "reason": "required contexts not green", "details": st}
    headers = _headers(os.getenv("GITHUB_TOKEN",""))
    with httpx.Client() as c:
        res = _merge_pr(c, info["owner"], info["repo"], info["number"], method=method, headers=headers)
        # update DB state
        row = (
            db.query(PullRequest)
            .filter(PullRequest.run_id == run_id)
            .order_by(PullRequest.created_at.desc())
            .first()
        )
        if row:
            row.state = "merged" if res.get("merged") else row.state
            db.commit()
        return {"merged": bool(res.get("merged")), "message": res.get("message"), "sha": res.get("sha")}

# --- Phase 8 helpers: refresh artifacts for any PR branch ---
import os, re, json
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
import httpx

from ..models import Project, RoadmapItem, PRD, DesignCheck, ResearchNote
from ..discovery import upsert_discovery_artifacts, dor_check

def _owner_repo_from_url(url: str) -> Optional[tuple[str, str]]:
    m = re.search(r"github\.com[:/]+([^/]+)/([^/.]+)", url or "")
    return (m.group(1), m.group(2)) if m else None

def _project_for_owner_repo(db: Session, owner: str, repo: str) -> Optional[Project]:
    # Fuzzy match on repo_url
    candidates = db.query(Project).all()
    for p in candidates:
        pair = _owner_repo_from_url(p.repo_url or "")
        if pair and pair == (owner, repo):
            return p
    return None

def _commit_artifacts_to_branch(db: Session, owner: str, repo: str, branch: str, project: Project, item: RoadmapItem, headers: dict):
    # Fetch latest artifacts for item
    prd = (
        db.query(PRD)
        .filter(PRD.project_id == project.id, PRD.roadmap_item_id == item.id)
        .order_by(PRD.created_at.desc())
        .first()
    )
    design = (
        db.query(DesignCheck)
        .filter(DesignCheck.project_id == project.id, DesignCheck.roadmap_item_id == item.id)
        .order_by(DesignCheck.created_at.desc())
        .first()
    )
    research = (
        db.query(ResearchNote)
        .filter(ResearchNote.project_id == project.id, ResearchNote.roadmap_item_id == item.id)
        .order_by(ResearchNote.created_at.desc())
        .first()
    )

    files: List[tuple[str, bytes]] = []
    base_dir = f"docs/roadmap/{item.id[:8]}-{_slug(item.title)}"
    if prd:
        files.append((f"{base_dir}/prd.json", json.dumps(prd.prd_json, indent=2).encode("utf-8")))
    if design:
        design_md = f"""# Design Heuristics Review

**Passes:** {design.passes}
**Score:** {design.heuristics_score}

_Accessibility notes:_
{design.a11y_notes}
"""
        files.append((f"{base_dir}/design.md", design_md.encode("utf-8")))
    if research:
        research_md = f"""# Research Summary

{research.summary}

## Evidence
""" + "\n".join([f"- {e}" for e in (research.evidence or [])])
        files.append((f"{base_dir}/research.md", research_md.encode("utf-8")))

    run_meta_path = f"{base_dir}/refresh.json"
    refresh_meta = {"project_id": project.id, "roadmap_item_id": item.id, "branch": branch}
    files.append((run_meta_path, json.dumps(refresh_meta, indent=2).encode("utf-8")))

    with httpx.Client() as c:
        for path, content in files:
            _put_file(c, owner, repo, path, content, f"chore(ai-csuite): refresh artifacts for {item.title}", branch, headers)

def _summarize_statuses(client: httpx.Client, owner: str, repo: str, sha: str) -> Dict[str, Any]:
    comb = _get_combined_status(client, owner, repo, sha, _headers(os.getenv("GITHUB_TOKEN","")))
    contexts = []
    for s in comb.get("statuses", []):
        contexts.append({
            "context": s.get("context"),
            "state": s.get("state"),
            "description": s.get("description"),
            "updated_at": s.get("updated_at"),
        })
    req = _required_contexts()
    state_map = {s["context"]: s["state"] for s in contexts}
    missing_ctx = [c for c in req if c not in state_map]
    not_green = [c for c in req if state_map.get(c) != "success"]
    can_merge = (len(missing_ctx) == 0 and len(not_green) == 0)
    return {
        "required_contexts": req,
        "statuses": contexts,
        "can_merge": can_merge,
        "missing_contexts": missing_ctx,
        "not_green": not_green,
        "overall": comb.get("state"),
    }

def ensure_and_update_for_branch_event(db: Session, owner: str, repo: str, branch: str, number: Optional[int] = None) -> Dict[str, Any]:
    """
    For any PR branch (opened/synchronize/reopened):
      - Find the Project by repo
      - Infer the roadmap_item_id prefix from branch name: feature/<8hex>-slug
      - Ensure (force) discovery artifacts
      - Commit refreshed artifacts to the PR branch
      - Update DOR + ARTIFACTS commit statuses (leave human approval unchanged)
      - Return a status summary (can_merge, contexts)
    """
    token = os.getenv("GITHUB_TOKEN")

    m = re.match(r"^feature/([0-9a-f]{8})-", branch)
    if not m:
        return {"skipped": "branch does not match feature/<8hex>-slug pattern"}

    prefix = m.group(1)
    project = _project_for_owner_repo(db, owner, repo)
    if not project:
        return {"skipped": f"no Project configured for {owner}/{repo}"}

    # Find item by id prefix
    item = (
        db.query(RoadmapItem)
        .filter(RoadmapItem.project_id == project.id, RoadmapItem.id.like(f"{prefix}%"))
        .first()
    )
    if not item:
        # Fallback: pick any item for this project (dev/test friendliness)
        item = (
            db.query(RoadmapItem)
            .filter(RoadmapItem.project_id == project.id)
            .first()
        )
        if not item:
            return {"skipped": f"no roadmap item with id prefix {prefix}"}

    # Ensure artifacts (force refresh)
    upsert_discovery_artifacts(db, item.tenant_id, project.id, item.id, force=True)

    headers = _headers(token)
    base_dir = f"docs/roadmap/{item.id[:8]}-{_slug(item.title)}"
    with httpx.Client() as c:
        # If writes are disabled OR token missing, return a dry-run summary
        if not _write_enabled() or not token:
            ok, missing, _ = dor_check(db, item.tenant_id, project.id, item.id)
            return {
                "dry_run": True,
                "owner": owner, "repo": repo, "branch": branch,
                "dor_pass": ok, "missing": missing, "base_dir": base_dir
            }

        _commit_artifacts_to_branch(db, owner, repo, branch, project, item, headers)
        head_ref = _get_ref(c, owner, repo, branch, headers)
        head_sha = head_ref["object"]["sha"]

        ok, missing, _ = dor_check(db, item.tenant_id, project.id, item.id)
        _set_status(c, owner, repo, head_sha, context=CTX_DOR,
                    state=("success" if ok else "failure"),
                    description=("DoR passed" if ok else f"DoR blocked: {', '.join(missing)}"),
                    headers=headers)
        _set_status(c, owner, repo, head_sha, context=CTX_ARTIFACTS,
                    state="success", description="Artifacts refreshed by AI‑CSuite", headers=headers)

        # Upsert summary comment (best-effort)
        try:
            # Try to find PR by head ref; if provided as 'number', prefer that
            pr_num = number
            if not pr_num:
                prs = c.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls", headers=headers,
                            params={"state": "open", "head": f"{owner}:{branch}"}, timeout=30)
                if prs.status_code == 200 and prs.json():
                    pr_num = prs.json()[0]["number"]
            if pr_num:
                comments = _list_issue_comments(c, owner, repo, pr_num, headers)
                cid = _find_marker_comment_id(comments, branch)
                body = build_pr_summary_md(project_name=project.name, item_title=item.title,
                                           branch=branch, dor_pass=ok, missing=missing,
                                           owner=owner, repo=repo, base_dir=base_dir)
                if cid:
                    _update_issue_comment(c, owner, repo, cid, body, headers)
                else:
                    _create_issue_comment(c, owner, repo, pr_num, body, headers)
        except Exception:
            pass

        summary = _summarize_statuses(c, owner, repo, head_sha)
        summary.update({"owner": owner, "repo": repo, "branch": branch, "head_sha": head_sha, "pr_number": number})
        return summary
