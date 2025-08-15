import os, uuid, httpx

BASE = os.getenv("ORCH_BASE", "http://localhost:8000")
TENANT = "00000000-0000-0000-0000-000000000000"


def _post_ok(path, payload):
    r = httpx.post(f"{BASE}{path}", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def _get_html(path):
    r = httpx.get(f"{BASE}{path}", timeout=60)
    r.raise_for_status()
    return r.text


def test_ui_root_and_run_page_contains_run_id():
    # GET /ui returns 200 and contains recognizable title
    html = _get_html("/ui")
    assert "Founder Cockpit" in html

    # Create project + item + run
    proj = _post_ok("/projects", {
        "tenant_id": TENANT,
        "name": f"UI-{uuid.uuid4().hex[:6]}",
        "description": "",
        "repo_url": ""  # ensure no live GH call required
    })

    item = _post_ok("/roadmap-items", {
        "tenant_id": TENANT,
        "project_id": proj["id"],
        "title": "UI Test"
    })

    run = _post_ok("/runs", {
        "tenant_id": TENANT,
        "project_id": proj["id"],
        "roadmap_item_id": item["id"],
        "phase": "delivery"
    })

    # GET /ui/run/{run_id} renders with the run id visible
    run_html = _get_html(f"/ui/run/{run['id']}")
    assert run["id"] in run_html


def test_ui_gates_approve_merge_when_dry_run():
    # Force dry-run for UI rendering via query param (does not depend on server env)
    html = _get_html("/ui/run/dummy-run-id?dry_run=1")
    assert "Dry‑run" in html or "Dry-run" in html
    # Buttons should render disabled attribute
    assert "approveBtn\" disabled" in html or "mergeBtn\" disabled" in html


