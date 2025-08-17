from fastapi.testclient import TestClient
from orchestrator.app import app


def test_phase43_roi_planning_endpoints():
    client = TestClient(app)

    # Seed attribution report
    att = client.post("/attribution/report/run", json={"from_date": "2025-01-01", "to_date": "2025-01-31"})
    assert att.status_code == 200, att.text
    report_id = att.json()["report_id"]

    # Seed experiment
    exp = client.post("/experiments/start", json={
        "experiment_id": "exp-1",
        "plan": {"variants": {"A": 0.6, "B": 0.4}},
        "seed": 123
    })
    assert exp.status_code == 200, exp.text

    # Compute ROI score for an idea
    body = {
        "tenant_id": "t-1",
        "project_id": "p-1",
        "idea_id": "roadmap:feat-1",
        "attribution_id": report_id,
        "experiment_id": "exp-1",
        "cost_cents": 500,
    }
    s = client.post("/planning/roi/score", headers={"X-Role": "admin"}, json=body)
    assert s.status_code == 200, s.text
    score = s.json()
    assert 0 <= score["score_bps"] <= 10000
    assert score["rationale"]["attribution"]["source_id"] == report_id
    assert score["rationale"]["experiment"]["experiment_id"] == "exp-1"

    # Suggest top opportunities for the project
    sug = client.post("/roadmap/suggest", headers={"X-Role": "viewer"}, json={"tenant_id": "t-1", "project_id": "p-1", "k": 5})
    assert sug.status_code == 200, sug.text
    top = sug.json()["top_opportunities"]
    assert isinstance(top, list)
    assert len(top) >= 1
    assert top[0]["idea_id"] == "roadmap:feat-1"
    assert "score_bps" in top[0]


