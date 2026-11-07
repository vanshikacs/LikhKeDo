import json

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app import evon
from app.config import get_settings
from app.main import app
from app.routes import health


def test_health(monkeypatch):
    async def up():
        return True

    async def down():
        return False, "unreachable"

    monkeypatch.setattr(health, "evon_health", down)
    monkeypatch.setattr(health, "_gnani_probe", up)
    health._cache.clear()
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["evon"] == "down" and body["gnani"] == "ok"
    assert body["evon_reason"] == "unreachable"
    assert body["queue"] == 0 and body["demo_only"] is False


@pytest.fixture
def evon_env(monkeypatch):
    st = get_settings()
    monkeypatch.setattr(st, "evon_base_url", "https://gpu.example/v1")
    monkeypatch.setattr(st, "evon_api_key", SecretStr("k"))

    def use(handler):
        real = httpx.AsyncClient

        def fake(*a, **kw):
            kw["transport"] = httpx.MockTransport(handler)
            return real(*a, **kw)

        monkeypatch.setattr(evon.httpx, "AsyncClient", fake)

    return use


@pytest.mark.parametrize("status,body,reason", [
    (200, {"data": [{"id": "gnani/gnani-evon-v3.3-30B-A3B"}]}, "ok"),
    (200, {"data": [{"id": "some/other-model"}]}, "model_missing"),
    (401, {"error": "bad key"}, "bad_key"),
    (404, {"detail": "Not Found"}, "bad_url"),
    (502, {}, "http_error"),
])
def test_evon_health_reasons(evon_env, status, body, reason):
    import asyncio

    seen = {}

    def handler(req: httpx.Request):
        seen["auth"] = req.headers.get("authorization")
        seen["url"] = str(req.url)
        return httpx.Response(status, content=json.dumps(body), headers={"content-type": "application/json"})

    evon_env(handler)
    ok, why = asyncio.run(evon.evon_health())
    assert (ok, why) == (reason == "ok", reason)
    assert seen["url"] == "https://gpu.example/v1/models" and seen["auth"] == "Bearer k"


def test_evon_health_unreachable_and_unconfigured(evon_env, monkeypatch):
    import asyncio

    def boom(req):
        raise httpx.ConnectError("refused")

    evon_env(boom)
    assert asyncio.run(evon.evon_health()) == (False, "unreachable")
    monkeypatch.setattr(get_settings(), "evon_base_url", None)
    assert asyncio.run(evon.evon_health()) == (False, "not_configured")


def test_demo_serves_only_live_runs(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "demo_dir", tmp_path)
    base = {"id": "x", "lang": "hi", "claims": []}
    for slug, meta in {"preview": {"source": "answer_key_preview", "lang": "hi"},
                       "nodate": {"source": "live", "lang": "hi"},
                       "real": {"source": "live", "lang": "hi", "live_run_at": "2026-11-08T10:00+00:00"}}.items():
        d = tmp_path / "cache" / slug
        d.mkdir(parents=True)
        (d / "report.json").write_text(json.dumps({**base, "demo": {**meta, "slug": slug}}), encoding="utf-8")
    c = TestClient(app)
    assert [d["slug"] for d in c.get("/api/demo").json()] == ["real"]
    assert c.get("/api/demo/real").status_code == 200
    assert c.get("/api/demo/preview").status_code == 404
    assert c.get("/api/demo/nodate").status_code == 404
    assert c.get("/api/demo/preview/slip").status_code == 404


def test_dev_pitch_only_in_debug(monkeypatch, tmp_path):
    st = get_settings()
    monkeypatch.setattr(st, "demo_dir", tmp_path)
    (tmp_path / "pitches").mkdir()
    (tmp_path / "pitches" / "hi_hinglish.wav").write_bytes(b"RIFF0000WAVE")
    c = TestClient(app)
    monkeypatch.setattr(st, "debug_save_audio", False)
    assert c.get("/api/dev/pitch/hi_hinglish").status_code == 404
    monkeypatch.setattr(st, "debug_save_audio", True)
    assert c.get("/api/dev/pitch/hi_hinglish").status_code == 200
    assert c.get("/api/dev/pitch/ta_tamil_english").status_code == 404
