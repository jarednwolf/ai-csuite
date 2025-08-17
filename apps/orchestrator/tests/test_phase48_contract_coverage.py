import os, json
from fastapi.testclient import TestClient
from orchestrator.app import app


def test_contract_coverage_report_artifact_and_db(tmp_path):
    client = TestClient(app)
    res = client.post("/quality/contracts/report", json={"seed": 123})
    assert res.status_code == 200, res.text
    report = res.json()
    assert report.get("version") == 1
    assert isinstance(report.get("schemas_present"), list)
    assert isinstance(report.get("docs_present"), dict)
    assert isinstance(report.get("tests_present"), list)
    # artifact exists with newline
    out_path = os.path.join("apps", "orchestrator", "orchestrator", "quality", "contracts_report.json")
    with open(out_path, "r", encoding="utf-8") as f:
        data = f.read()
    assert data.endswith("\n")
    j = json.loads(data)
    assert j.get("version") == 1


