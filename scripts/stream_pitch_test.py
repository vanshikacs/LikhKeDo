"""End-to-end Listen test without a browser: stream demo/pitches/<slug>.wav through OUR backend's WebSocket
(/api/cases/<id>/listen -> Prisma streaming) at real time, exactly like the browser worklet (16 kHz PCM16,
1024-byte frames every 32 ms), then compare the live captions with the pitch text.

Needs the backend running (uvicorn on :8000). Spends one Prisma streaming session.
  backend/.venv/Scripts/python scripts/stream_pitch_test.py [--slug hi_hinglish] [--api http://localhost:8000]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import httpx  # noqa: E402
import websockets  # noqa: E402
from rapidfuzz import fuzz  # noqa: E402

from app.gnani import to_pcm16k  # noqa: E402

LANG = {"hi_hinglish": "hi", "ta_tamil_english": "ta", "mr_marathi": "mr"}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default="hi_hinglish")
    ap.add_argument("--api", default="http://localhost:8000")
    a = ap.parse_args()
    lang = LANG[a.slug]
    pcm = to_pcm16k((ROOT / "demo/pitches" / f"{a.slug}.wav").read_bytes())
    ref = (ROOT / "demo/pitches" / f"{a.slug}.txt").read_text(encoding="utf-8")
    async with httpx.AsyncClient(base_url=a.api) as c:
        cid = (await c.post("/api/cases", json={"lang": lang, "mode": "listen", "consent": True})).json()["id"]
    url = a.api.replace("http", "ws", 1) + f"/api/cases/{cid}/listen"
    captions: dict[int, str] = {}
    flags: list[str] = []
    events: list[str] = []
    t_connected = t_first_text = None
    t0 = time.perf_counter()
    async with websockets.connect(url, max_size=None) as ws:
        await ws.send(json.dumps({"lang": lang, "sample_rate": 16000}))

        async def receive():
            nonlocal t_connected, t_first_text
            async for m in ws:
                ev = json.loads(m)
                events.append(ev["type"])
                if ev["type"] == "connected":
                    t_connected = time.perf_counter() - t0
                elif ev["type"] == "transcript" and ev.get("text"):
                    t_first_text = t_first_text or time.perf_counter() - t0
                    captions[ev.get("segment_index", len(captions))] = ev["text"]
                elif ev["type"] == "redflag":
                    flags.append(ev["phrase"])
                elif ev["type"] == "error":
                    print("ERROR", ev)
                elif ev["type"] == "closed":
                    return

        rx = asyncio.create_task(receive())
        while t_connected is None and time.perf_counter() - t0 < 10:
            await asyncio.sleep(0.05)
        start = time.perf_counter()
        for n, i in enumerate(range(0, len(pcm), 1024)):
            frame = pcm[i:i + 1024]
            await ws.send(frame + bytes(1024 - len(frame)))
            ahead = start + (n + 1) * 0.032 - time.perf_counter()
            if ahead > 0:
                await asyncio.sleep(ahead)
            if rx.done():
                break  # the server closed the session (an error was printed)
        if not rx.done():
            await ws.send(json.dumps({"type": "stop"}))
            await asyncio.wait_for(rx, timeout=30)
    text = " ".join(captions[k] for k in sorted(captions))
    sim = fuzz.ratio(ref.replace("\n", " "), text)
    print(f"{a.slug}: audio {len(pcm) / 32000:.1f}s, connected {t_connected or -1:.2f}s, first caption {t_first_text or 0:.2f}s, "
          f"{len(captions)} segments, similarity to pitch text {sim:.0f}%")
    print(f"red flags: {sorted(set(flags))}")
    print(f"events: { {e: events.count(e) for e in set(events)} }")
    print("captions:\n  " + "\n  ".join(captions[k] for k in sorted(captions)))
    async with httpx.AsyncClient(base_url=a.api) as c:
        await c.delete(f"/api/cases/{cid}")


if __name__ == "__main__":
    asyncio.run(main())
