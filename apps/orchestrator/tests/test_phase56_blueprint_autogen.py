import httpx


def test_blueprint_scaffold_endpoint_happy_path():
    # Pick an existing manifest id from the registry (from Phase 26)
    bp_id = "web-crud-fastapi-postgres-react"
    r = httpx.post("http://127.0.0.1:8001/self/blueprints/scaffold", json={"blueprint_id": bp_id}, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["blueprint_id"] == bp_id
    assert data["op_id"]
    assert isinstance(data.get("generated"), list)


