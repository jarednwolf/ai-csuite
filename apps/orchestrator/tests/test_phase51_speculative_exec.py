import os, json
from fastapi.testclient import TestClient
from orchestrator.app import app


def test_speculative_exec_report_and_persist():
    client = TestClient(app)
    res = client.post("/self/speculate", json={"description": "try patch", "seed": 124})
    assert res.status_code == 200, res.text
    report = res.json()
    assert report.get("version") == 1
    assert "metrics" in report
    # file artifact
    path = os.path.join("apps", "orchestrator", "orchestrator", "self", "spec_report.json")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    assert text.endswith("\n")
    j = json.loads(text)
    assert j.get("seed") == 124


