import asyncio
import json
import threading
import time

import pytest
import websockets
from fastapi.testclient import TestClient
from sqlmodel import select

from app import db, gnani, stream_proxy
from app.config import get_settings
from app.main import app
from app.redflags import find_redflags


class FakePrisma:
    """websockets.serve in its own thread/loop; records frames and replies like Prisma."""

    def __init__(self, close_after_connect=False):
        self.frames: list[int] = []
        self.headers: dict = {}
        self.commit = False
        self.close_after_connect = close_after_connect
        self.loop = asyncio.new_event_loop()
        self.port = None
        ready = threading.Event()

        async def handler(ws):
            self.headers = dict(ws.request.headers)
            await ws.send(json.dumps({"type": "connected", "request_id": "fake-rid"}))
            if self.close_after_connect:
                await ws.close(1008, "bad header")
                return
            async for m in ws:
                if isinstance(m, bytes):
                    self.frames.append(len(m))
                    if len(self.frames) == 3:
                        await ws.send(json.dumps({"type": "transcript", "segment_index": 0,
                                                  "text": "सर, returns guaranteed हैं, बिल्कुल FD जैसा",
                                                  "detected_language_code": "hi-IN", "latency": 0.2}))
                elif json.loads(m).get("type") == "commit":
                    self.commit = True
                    await ws.send(json.dumps({"type": "transcript", "segment_index": 1,
                                              "text": "सिर्फ़ 5 साल premium", "detected_language_code": "hi-IN"}))
                    await ws.close()
                    return

        async def main():
            self.server = await websockets.serve(handler, "127.0.0.1", 0)
            self.port = self.server.sockets[0].getsockname()[1]
            ready.set()
            await self.server.wait_closed()

        self.thread = threading.Thread(target=lambda: self.loop.run_until_complete(main()), daemon=True)
        self.thread.start()
        ready.wait(5)

    def stop(self):
        self.loop.call_soon_threadsafe(self.server.close)
        self.thread.join(5)


@pytest.fixture
def fake(monkeypatch):
    f = FakePrisma()
    monkeypatch.setattr(stream_proxy, "WS_URL", f"ws://127.0.0.1:{f.port}")
    monkeypatch.setattr(gnani, "gate", gnani.GnaniGate())
    monkeypatch.setattr(get_settings(), "stream_holds_lock", True)  # exercise the lock path
    yield f
    f.stop()


def make_case(consent=True):
    with db.session() as s:
        c = db.Case(lang="hi", mode="listen", consent=consent)
        s.add(c)
        s.commit()
        return c.id


def collect(ws, until="closed", limit=50):
    out = []
    for _ in range(limit):
        m = json.loads(ws.receive_text())
        out.append(m)
        if m["type"] == until:
            break
    return out


def test_redflag_rules():
    assert set(find_redflags("returns guaranteed हैं, बिल्कुल FD जैसा")) == {"guaranteed", "FD jaisa"}
    assert "sirf N saal" in find_redflags("सिर्फ़ 5 साल premium")
    assert "no lock-in" in find_redflags("uske baad lock-in nahi")
    assert find_redflags("नमस्ते सर") == []
    # real Prisma v3.0 codemix output (numbers as words)
    real = "सर, यह plan बिल्कुल FD जैसा है, इसमें returns guaranteed हैं, हर साल minimum बारह percent मिलेगा। आपको सिर्फ पाँच साल premium भरना है।"
    assert set(find_redflags(real)) == {"guaranteed", "FD jaisa", "sirf N saal"}
    assert "sirf N saal" in find_redflags("5 வருஷம் மட்டும் premium") and "sirf N saal" in find_redflags("फक्त पाच वर्षं")


def test_forwarding_redflags_segments_and_lock_release(fake):
    cid = make_case()
    with TestClient(app) as client:
        with client.websocket_connect(f"/api/cases/{cid}/listen") as ws:
            ws.send_text(json.dumps({"lang": "hi"}))
            # 3.5 frames worth, sent in odd sizes: proxy must re-buffer to exact 1024-byte frames
            ws.send_bytes(b"\x01" * 1500)
            ws.send_bytes(b"\x02" * 2084)
            time.sleep(0.3)
            ws.send_text(json.dumps({"type": "stop"}))
            msgs = collect(ws)
    assert fake.headers["model"] == "prisma-v3.0"
    assert fake.headers["language_code"] == "hi-IN"
    assert fake.headers["x-sample-rate"] == "16000" and fake.headers["format"] == "codemix"
    assert fake.headers["x-api-key-id"] == "test-key"
    assert set(fake.frames) == {1024} and len(fake.frames) == 4 and fake.commit
    types = [m["type"] for m in msgs]
    assert "transcript" in types and types[-1] == "closed"
    flags = {m["phrase"] for m in msgs if m["type"] == "redflag"}
    assert {"guaranteed", "FD jaisa", "sirf N saal"} <= flags
    with db.session() as s:
        segs = list(s.exec(select(db.Segment).where(db.Segment.case_id == cid).order_by(db.Segment.idx)))
        call = s.exec(select(db.ApiCall).where(db.ApiCall.service == "prisma-stream")).first()
    assert [x.idx for x in segs] == [0, 1]
    assert call.request_id == "fake-rid"
    assert gnani.gate.queue == 0


def test_browser_disconnect_releases_lock(fake):
    cid = make_case()
    with TestClient(app) as client:
        with client.websocket_connect(f"/api/cases/{cid}/listen") as ws:
            ws.send_text(json.dumps({"lang": "hi"}))
            ws.send_bytes(b"\x00" * 1024)
            time.sleep(0.2)
        # leaving the block disconnects the browser abruptly
        for _ in range(50):
            if gnani.gate.queue == 0:
                break
            time.sleep(0.05)
    assert gnani.gate.queue == 0


def test_prisma_close_1008_reports_error(monkeypatch):
    f = FakePrisma(close_after_connect=True)
    monkeypatch.setattr(stream_proxy, "WS_URL", f"ws://127.0.0.1:{f.port}")
    monkeypatch.setattr(gnani, "gate", gnani.GnaniGate())
    try:
        cid = make_case()
        with TestClient(app) as client:
            with client.websocket_connect(f"/api/cases/{cid}/listen") as ws:
                ws.send_text(json.dumps({"lang": "hi"}))
                msgs = collect(ws)
        errs = [m for m in msgs if m["type"] == "error"]
        assert errs and errs[0]["code"] == "CLOSED_1008"
        assert gnani.gate.queue == 0
    finally:
        f.stop()


def test_listen_requires_consent(fake):
    cid = make_case(consent=False)
    with TestClient(app) as client:
        with client.websocket_connect(f"/api/cases/{cid}/listen") as ws:
            m = json.loads(ws.receive_text())
    assert m["code"] == "NO_CONSENT"
