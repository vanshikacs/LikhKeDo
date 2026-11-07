"""Prisma smoke test: REST /stt/v3, optional streaming and keyterm comparison.

Usage (from the repo root, backend venv):
  backend/.venv/Scripts/python scripts/smoke_prisma.py demo/test_clips/clip1.wav
  ... --stream               also send the clip through the streaming API
  ... --compare-keyterms     REST twice: without and with the finance keyterm list
  ... --keyterms             send the finance keyterm list on the REST call
  ... --lang hi-IN,en-IN --format codemix

Each REST call and each streaming session spends Gnani credits.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import sys
import time
import wave
from pathlib import Path

import httpx

from gnani_common import (FINANCE_TERMS, MAX_REST_SECONDS, PRISMA_MODEL, REST_BASE, error_code,
                          rest_headers, stream_pcm, wav_to_pcm16_mono_16k)


def pcm_to_wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm)
    return buf.getvalue()


def rest_call(wav_bytes: bytes, name: str, lang: str, fmt: str, keyterms: list[str] | None) -> dict:
    data = {"model": PRISMA_MODEL, "language_code": lang, "format": fmt}
    if keyterms:
        data["keyterms"] = json.dumps(keyterms)
    t0 = time.perf_counter()
    r = httpx.post(f"{REST_BASE}/stt/v3", headers=rest_headers(), data=data,
                   files={"audio_file": (name, wav_bytes, "audio/wav")}, timeout=60)
    wall = time.perf_counter() - t0
    out = {"status": r.status_code, "wall_s": round(wall, 2)}
    if r.status_code == 200:
        out.update(r.json())
    else:
        out["error"] = error_code(r)
    return out


def print_rest(label: str, res: dict) -> None:
    print(f"--- REST {label} ---")
    print(f"status: {res['status']}  wall: {res['wall_s']} s")
    if res["status"] != 200:
        print(f"error: {res.get('error')}")
        return
    for k in ("success", "request_id", "model", "detected_language_code", "processing_time",
              "end_to_end_latency"):
        print(f"{k}: {res.get(k)}")
    print(f"transcript: {res.get('transcript')}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("wav", type=Path)
    p.add_argument("--lang", default="hi-IN,en-IN")
    p.add_argument("--format", default="codemix")
    p.add_argument("--keyterms", action="store_true", help="send the finance keyterm list")
    p.add_argument("--stream", action="store_true", help="also test the streaming API")
    p.add_argument("--compare-keyterms", action="store_true")
    a = p.parse_args()

    if not a.wav.exists():
        sys.exit(f"{a.wav} not found")
    pcm = wav_to_pcm16_mono_16k(a.wav)
    seconds = len(pcm) / 32000
    if seconds > MAX_REST_SECONDS:
        sys.exit(f"clip is {seconds:.1f} s; Prisma REST accepts at most 30 s")
    wav_bytes = pcm_to_wav(pcm)
    print(f"clip: {a.wav.name}, {seconds:.1f} s (sent as 16 kHz mono PCM16 WAV)")

    summary = []
    calls = 0
    if a.compare_keyterms:
        plain = rest_call(wav_bytes, a.wav.name, a.lang, a.format, None)
        boosted = rest_call(wav_bytes, a.wav.name, a.lang, a.format, FINANCE_TERMS)
        calls += 2
        print_rest("without keyterms", plain)
        print_rest("with keyterms", boosted)
        print("--- side by side ---")
        print(f"WITHOUT: {plain.get('transcript', plain.get('error'))}")
        print(f"WITH:    {boosted.get('transcript', boosted.get('error'))}")
        summary.append(f"keyterms compare: transcripts {'identical' if plain.get('transcript') == boosted.get('transcript') else 'differ'}")
        rest = boosted
    else:
        rest = rest_call(wav_bytes, a.wav.name, a.lang, a.format, FINANCE_TERMS if a.keyterms else None)
        calls += 1
        print_rest("with keyterms" if a.keyterms else "", rest)
    summary.insert(0, f"Prisma REST {seconds:.1f}s clip -> HTTP {rest['status']}, "
                      f"lang={rest.get('detected_language_code')}, processing={rest.get('processing_time')}, "
                      f"e2e={rest.get('end_to_end_latency')}, wall={rest['wall_s']}s")

    if a.stream:
        print("--- STREAM ---")
        res = asyncio.run(stream_pcm(pcm, a.lang.split(",")[0], a.format, FINANCE_TERMS if a.keyterms else None))
        calls += 1
        print("message types:", " ".join(res["types"]))
        print("full streamed transcript:", " ".join(t.get("text", "") for t in res["transcripts"]))
        first = res["first_transcript_s"]
        summary.append(f"Prisma stream: {res['frames']} frames, {len(res['transcripts'])} transcript msgs, "
                       f"first after {first:.2f}s" if first is not None else
                       f"Prisma stream: {res['frames']} frames, no transcript, errors={res['errors']}")

    print(f"\nGnani calls made: {calls}")
    print("SUMMARY: " + "; ".join(summary))


if __name__ == "__main__":
    main()
