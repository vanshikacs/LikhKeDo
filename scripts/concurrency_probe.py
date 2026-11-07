"""Does an open Prisma streaming session block other Gnani calls?

Opens a Prisma streaming session, and once the server says 'connected' fires ONE Timbre REST call
while audio is still streaming. Reports whether Timbre returned 429 RATE_LIMITED.

Usage (from the repo root, backend venv):
  backend/.venv/Scripts/python scripts/concurrency_probe.py [--wav demo/test_clips/clip1.wav]
Without --wav it streams 8 s of silence. Spends credits for 1 stream + 1 TTS call.
"""
from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path

import httpx

from gnani_common import REST_BASE, error_code, rest_headers, stream_pcm, wav_to_pcm16_mono_16k

TTS_BODY = {
    "text": "यह एक छोटा टेस्ट है।",
    "voice": "Tarika",
    "model": "timbre-v3.0",
    "language": "hi-IN",
    "audio_config": {"sample_rate": 24000, "num_channels": 1, "sample_width": 2,
                     "encoding": "linear_pcm", "container": "wav"},
}


async def fire_tts() -> dict:
    await asyncio.sleep(1.0)  # make sure audio frames are already flowing
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{REST_BASE}/api/v1/tts/inference", headers=rest_headers(), json=TTS_BODY)
    res = {"status": r.status_code, "wall_s": round(time.perf_counter() - t0, 2)}
    if r.status_code != 200:
        res["error"] = error_code(r)
    print(f"  >>> Timbre during stream: HTTP {res['status']} in {res['wall_s']} s "
          f"{res.get('error', '')}")
    return res


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--wav", type=Path)
    a = p.parse_args()
    pcm = wav_to_pcm16_mono_16k(a.wav) if a.wav else b"\x00" * (32000 * 8)

    res = asyncio.run(stream_pcm(pcm, "hi-IN", "codemix", None, on_connected=fire_tts))
    tts = res.get("side_result") or {}
    status = tts.get("status")
    if status == 429:
        verdict = "YES - streaming blocks other calls (Timbre got 429 RATE_LIMITED)"
    elif status == 200:
        verdict = "NO - Timbre succeeded while a stream was open"
    else:
        verdict = f"UNCLEAR - Timbre returned HTTP {status} {tts.get('error', '')}"
    if res["errors"]:
        verdict += f"; stream errors: {res['errors']}"
    print("\nGnani calls made: 2 (1 stream + 1 TTS)")
    print(f"SUMMARY: Streaming blocks TTS? {verdict}")


if __name__ == "__main__":
    main()
