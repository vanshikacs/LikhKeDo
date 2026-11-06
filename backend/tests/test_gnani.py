import asyncio
import io
import json
import wave

import httpx
import pytest
from sqlmodel import select

from app import db
from app.gnani import GnaniClient, GnaniError, GnaniGate, split_on_silence, split_text


def wav_bytes(seconds=1.0, rate=16000, tone=True):
    import math
    n = int(seconds * rate)
    frames = b"".join(int(8000 * math.sin(i / 10) if tone else 0).to_bytes(2, "little", signed=True)
                      for i in range(n))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)
    return buf.getvalue()


def ok_prisma(text="नमस्ते", rid="r-1"):
    return httpx.Response(200, json={"success": True, "request_id": rid, "transcript": text,
                                     "model": "prisma-v3.0", "detected_language_code": "hi-IN",
                                     "processing_time": 0.5, "end_to_end_latency": 0.6})


async def no_sleep(_):
    return None


def client(handler, **kw):
    return GnaniClient(transport=httpx.MockTransport(handler), sleep=kw.get("sleep", no_sleep),
                       gate_=kw.get("gate", GnaniGate()))


def test_request_has_documented_fields_only():
    seen = {}

    def handler(req: httpx.Request):
        seen["key"] = req.headers.get("x-api-key-id")
        seen["body"] = req.content
        return ok_prisma()

    res = asyncio.run(client(handler).transcribe_rest(wav_bytes(), "a.wav", "hi-IN,en-IN", keyterms=["FD"]))
    assert res.text == "नमस्ते" and res.request_ids == ["r-1"]
    assert seen["key"] == "test-key"
    body = seen["body"].decode("latin-1")
    for f in ('name="model"', "prisma-v3.0", 'name="language_code"', 'name="format"', "codemix",
              'name="keyterms"', 'name="audio_file"'):
        assert f in body


def test_lock_serialises_concurrent_calls():
    active, peak = 0, 0

    async def run():
        nonlocal active, peak
        g = GnaniGate()

        async def handler(req):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.05)
            active -= 1
            return ok_prisma()

        c = GnaniClient(transport=httpx.MockTransport(handler), sleep=no_sleep, gate_=g)
        # different audio so the cache can't short-circuit the second call
        await asyncio.gather(c.transcribe_rest(wav_bytes(1.0), "a.wav", "hi-IN"),
                             c.transcribe_rest(wav_bytes(1.2), "b.wav", "hi-IN"))
        assert g.queue == 0

    asyncio.run(run())
    assert peak == 1


def test_429_then_200_succeeds_after_backoff():
    calls, sleeps = [], []

    def handler(req):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, json={"error_code": "RATE_LIMITED"})
        return ok_prisma()

    async def rec_sleep(s):
        sleeps.append(s)

    res = asyncio.run(client(handler, sleep=rec_sleep).transcribe_rest(wav_bytes(), "a.wav", "hi-IN"))
    assert res.text == "नमस्ते"
    assert len(calls) == 2 and sleeps == [0.5]
    with db.session() as s:
        rows = list(s.exec(select(db.ApiCall)))
    assert [r.status for r in rows] == [429, 200]


def test_400_is_not_retried():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(400, json={"error_code": "EMPTY_AUDIO"})

    with pytest.raises(GnaniError) as e:
        asyncio.run(client(handler).transcribe_rest(wav_bytes(), "a.wav", "hi-IN"))
    assert e.value.code == "EMPTY_AUDIO" and e.value.http_status == 400
    assert len(calls) == 1


def test_gives_up_after_three_retries():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(503, json={})

    with pytest.raises(GnaniError):
        asyncio.run(client(handler).transcribe_rest(wav_bytes(), "a.wav", "hi-IN"))
    assert len(calls) == 4


def test_prisma_cache_hit_skips_network():
    calls = []

    def handler(req):
        calls.append(1)
        return ok_prisma()

    c = client(handler)
    audio = wav_bytes()
    asyncio.run(c.transcribe_rest(audio, "a.wav", "hi-IN"))
    again = asyncio.run(c.transcribe_rest(audio, "a.wav", "hi-IN"))
    assert again.cached and len(calls) == 1


def test_tts_cache_and_fallback_on_400():
    bodies = []

    def handler(req):
        body = json.loads(req.content)
        bodies.append(body)
        if "speed" in body:
            return httpx.Response(400, json={"error_code": "INVALID_PARAM"})
        return httpx.Response(200, content=wav_bytes(0.5, 48000), headers={"content-type": "audio/wav"})

    c = client(handler)
    wav, meta = asyncio.run(c.synthesize("नमस्ते पापा।", "hi-IN"))
    assert wav[:4] == b"RIFF" and meta["model"] == "timbre-v3.0"
    assert bodies[0]["speed"] == 0.9 and bodies[0]["audio_config"]["sample_rate"] == 24000
    assert "speed" not in bodies[1] and bodies[1]["audio_config"]["sample_rate"] == 48000
    n = len(bodies)
    wav2, meta2 = asyncio.run(c.synthesize("नमस्ते पापा।", "hi-IN"))
    assert meta2["cached"] and len(bodies) == n and wav2 == wav


def test_split_text_and_silence():
    long = "। ".join(["यह एक वाक्य है"] * 60) + "।"
    parts = split_text(long, 450)
    assert all(len(p) <= 450 for p in parts) and len(parts) > 1
    pcm = b"\x10\x00" * (16000 * 60)  # 60 s
    chunks = split_on_silence(pcm, 25)
    assert all(len(c) <= 25 * 32000 for c in chunks)
    assert sum(len(c) for c in chunks) == len(pcm)
