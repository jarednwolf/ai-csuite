from fastapi.testclient import TestClient
from orchestrator.app import app


def test_repo_map_and_hotspots_and_ownership():
    client = TestClient(app)

    m = client.get("/repo/map").json()
    assert isinstance(m, dict)
    assert m.get("version") == 1
    assert isinstance(m.get("files"), list)
    assert isinstance(m.get("modules"), dict)

    hs = client.get("/repo/hotspots").json()
    assert isinstance(hs, dict)
    assert hs.get("version") == 1
    assert isinstance(hs.get("hotspots"), list)
    assert all("path" in x and "score" in x for x in hs.get("hotspots"))

    own = client.get("/repo/ownership").json()
    assert own.get("version") == 1
    assert isinstance(own.get("owners"), dict)


