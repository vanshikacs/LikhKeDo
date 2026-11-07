import json
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app import db, gnani
from app.evon import EvonClient
from app.main import app
from app.routes import cases, health

from .fake_evon import FakeOpenAI
from .test_gnani import wav_bytes
from .test_pipeline import EXTRACT, PITCH, verify


@pytest.fixture
def client(monkeypatch):
    def handler(req: httpx.Request):
        if req.url.path == "/stt/v3":
            return httpx.Response(200, json={"success": True, "request_id": "prisma-rid-1", "transcript": PITCH,
                                             "model": "prisma-v3.0", "detected_language_code": "hi-IN",
                                             "processing_time": 0.4, "end_to_end_latency": 0.5})
        return httpx.Response(200, content=wav_bytes(0.3, 24000), headers={"content-type": "audio/wav"})

    async def no_sleep(_):
        return None

    gnani.set_client(gnani.GnaniClient(transport=httpx.MockTransport(handler), sleep=no_sleep, gate_=gnani.GnaniGate()))

    async def up():
        return True, "ok"

    monkeypatch.setattr(cases, "evon_status", up)
    monkeypatch.setattr(cases, "evon_factory", lambda: EvonClient(FakeOpenAI(EXTRACT, verify)))
    cases._rate.clear()
    with TestClient(app) as c:
        yield c
    gnani.set_client(None)


def new_case(c, **kw):
    r = c.post("/api/cases", json={"lang": "hi", "mode": "recall", "consent": True, **kw})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_happy_path(client):
    cid = new_case(client)
    r = client.post(f"/api/cases/{cid}/recall", content=wav_bytes(2.0), headers={"content-type": "audio/wav"})
    assert r.status_code == 200, r.text
    assert r.json()["request_ids"] == ["prisma-rid-1"]
    r = client.post(f"/api/cases/{cid}/document", json={"demo_doc": "suraksha_plus"})
    assert r.status_code == 200 and r.json()["clauses"] == 19
    r = client.post(f"/api/cases/{cid}/analyze")
    assert r.status_code == 200, r.text
    with client.stream("GET", f"/api/cases/{cid}/progress") as s:
        events = [json.loads(line[6:]) for line in s.iter_lines() if line.startswith("data: ")]
    assert events[-1]["stage"] == "done"
    assert any(e.get("stage") == "checking" for e in events)

    rep = client.get(f"/api/cases/{cid}/report").json()
    assert rep["status"] == "done" and len(rep["claims"]) == 6
    assert rep["counts"] == {"WRITTEN": 2, "CONTRADICTED": 2, "NOT_IN_WRITING": 2}
    assert rep["trace"]["evon_model"] == "gnani/gnani-evon-v3.3-30B-A3B"
    assert any(c["request_id"] == "prisma-rid-1" for c in rep["trace"]["calls"])
    assert rep["disclaimer"] == "Not financial or legal advice."

    r = client.post(f"/api/cases/{cid}/speak", json={"target": "summary"})
    assert r.status_code == 200 and r.content[:4] == b"RIFF"
    r = client.post(f"/api/cases/{cid}/speak", json={"target": rep["claims"][0]["id"]})
    assert r.status_code == 200
    slip = client.get(f"/api/cases/{cid}/slip").text
    assert "लिख के दो" in slip and "Not financial or legal advice" in slip
    assert rep["claims"][0]["quote"] in slip       # contradicted promise listed
    assert client.delete(f"/api/cases/{cid}").json() == {"deleted": True}
    assert client.get(f"/api/cases/{cid}/report").status_code == 404


def test_validation(client):
    assert client.post("/api/cases", json={"lang": "xx", "mode": "recall", "consent": True}).status_code == 422
    assert client.post("/api/cases", json={"lang": "hi", "mode": "recall", "consent": False}).status_code == 422
    cid = new_case(client)
    assert client.post(f"/api/cases/{cid}/document", content=b"hello", headers={"content-type": "application/pdf"}).status_code == 400
    assert client.post(f"/api/cases/{cid}/recall", content=wav_bytes(31.5), headers={"content-type": "audio/wav"}).status_code == 400
    r = client.post(f"/api/cases/{cid}/analyze")
    assert r.status_code == 400 and "record" in r.json()["detail"]
    assert client.get("/api/cases/nope/report").status_code == 404
    big = b"%PDF" + b"0" * (5 * 1024 * 1024 + 10)
    assert client.post(f"/api/cases/{cid}/document", content=big, headers={"content-type": "application/pdf"}).status_code == 413


def test_analyze_503_when_evon_down(client, monkeypatch):
    async def down():
        return False, "unreachable"

    monkeypatch.setattr(cases, "evon_status", down)
    cid = new_case(client)
    r = client.post(f"/api/cases/{cid}/analyze")
    d = r.json()["detail"]
    assert r.status_code == 503 and d["demo"].startswith("/api/demo/") and d["reason"] == "unreachable"


def test_rate_limit(client, monkeypatch):
    monkeypatch.setattr(cases, "_rate_ok", lambda ip: False)
    cid = new_case(client)
    client.post(f"/api/cases/{cid}/recall", content=wav_bytes(1.0), headers={"content-type": "audio/wav"})
    client.post(f"/api/cases/{cid}/document", json={"demo_doc": "suraksha_plus"})
    assert client.post(f"/api/cases/{cid}/analyze").status_code == 429


def test_purge_expired(client):
    cid = new_case(client)
    with db.session() as s:
        c = s.get(db.Case, cid)
        c.expires_at = db.now() - timedelta(minutes=1)
        s.add(c)
        s.commit()
    assert db.purge_expired() == 1
    assert client.get(f"/api/cases/{cid}/report").status_code == 404


def test_admin_requires_secret(client):
    assert client.post("/api/admin/purge").status_code == 403
    assert client.post("/api/admin/purge", headers={"X-Admin-Secret": "test-admin"}).status_code == 200


def test_demo_missing_is_404(client):
    assert client.get("/api/demo/does_not_exist").status_code == 404
    assert client.get("/api/demo/..%2f..").status_code == 404
