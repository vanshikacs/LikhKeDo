from fastapi.testclient import TestClient

from app.main import app
from app.routes import health


def test_health(monkeypatch):
    async def up():
        return True

    async def down():
        return False

    monkeypatch.setattr(health, "evon_health", down)
    monkeypatch.setattr(health, "_gnani_probe", up)
    health._cache.clear()
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["evon"] == "down" and body["gnani"] == "ok"
    assert body["queue"] == 0 and body["demo_only"] is False
