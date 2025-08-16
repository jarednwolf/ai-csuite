from fastapi.testclient import TestClient
from orchestrator.app import app
import os, json, tempfile, shutil


def test_blueprints_list_and_get_valid():
    client = TestClient(app)
    r = client.get("/blueprints")
    assert r.status_code == 200, r.text
    items = r.json()
    assert isinstance(items, list)
    # Expect at least two manifests present
    ids = {i["id"] for i in items}
    assert "web-crud-fastapi-postgres-react" in ids
    assert "ai-chat-agent-web" in ids

    # Fetch full manifest
    r2 = client.get("/blueprints/web-crud-fastapi-postgres-react")
    assert r2.status_code == 200, r2.text
    mf = r2.json()
    # Required fields
    assert mf["id"] == "web-crud-fastapi-postgres-react"
    assert mf["version"]
    assert mf["stack"]["backend"]["framework"] == "fastapi"



