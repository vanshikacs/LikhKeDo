"""Timbre smoke test: POST /api/v1/tts/inference and save the WAV.

Usage (from the repo root, backend venv):
  backend/.venv/Scripts/python scripts/smoke_timbre.py "नमस्ते, यह एक टेस्ट है।"
  ... --model timbre-v2.5 --voice Poorvi --lang hi-en --out out.wav

Tries speed 0.9 + 24000 Hz first; on HTTP 400 retries without speed at 48000 Hz.
Each attempt spends Gnani credits.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx

from gnani_common import REST_BASE, error_code, rest_headers, wav_duration

ATTEMPTS = [
    {"label": "speed=0.9, 24000 Hz", "speed": 0.9, "sample_rate": 24000},
    {"label": "no speed, 48000 Hz", "speed": None, "sample_rate": 48000},
]


def body(text: str, voice: str, model: str, lang: str, speed, sample_rate: int) -> dict:
    b = {
        "text": text,
        "voice": voice,
        "model": model,
        "language": lang,
        "audio_config": {
            "sample_rate": sample_rate,
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": "wav",
        },
    }
    if speed is not None:
        b["speed"] = speed
    return b


def synth(text: str, voice: str, model: str, lang: str, speed, sample_rate: int) -> tuple[httpx.Response, float]:
    t0 = time.perf_counter()
    r = httpx.post(f"{REST_BASE}/api/v1/tts/inference", headers=rest_headers(),
                   json=body(text, voice, model, lang, speed, sample_rate), timeout=60)
    return r, time.perf_counter() - t0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("text")
    p.add_argument("--model", default="timbre-v3.0")
    p.add_argument("--voice", default="Tarika")
    p.add_argument("--lang", default="hi-IN")
    p.add_argument("--out", type=Path, default=Path("out.wav"))
    a = p.parse_args()

    print(f"text: {len(a.text)} chars, model={a.model}, voice={a.voice}, language={a.lang}")
    calls = 0
    for att in ATTEMPTS:
        r, wall = synth(a.text, a.voice, a.model, a.lang, att["speed"], att["sample_rate"])
        calls += 1
        ctype = r.headers.get("content-type", "")
        print(f"--- attempt: {att['label']} ---")
        print(f"status: {r.status_code}  content-type: {ctype}  bytes: {len(r.content)}  wall: {wall:.2f} s")
        if r.status_code == 200:
            a.out.write_bytes(r.content)
            try:
                dur = f"{wav_duration(r.content):.2f}s"
            except Exception as e:  # not a parseable WAV
                dur = f"unreadable ({e})"
            print(f"saved: {a.out}  duration: {dur}")
            print(f"\nGnani calls made: {calls}")
            print(f"SUMMARY: Timbre {a.model}/{a.voice}/{a.lang} {len(a.text)} chars -> HTTP 200 with "
                  f"[{att['label']}], {len(r.content)} bytes, {dur} audio, wall={wall:.2f}s")
            return
        print(f"error: {error_code(r)}")
        if r.status_code != 400:
            break  # only a 400 means "try the other combination"
    print(f"\nGnani calls made: {calls}")
    print(f"SUMMARY: Timbre {a.model}/{a.voice}/{a.lang} FAILED, last HTTP {r.status_code} {error_code(r)}")
    sys.exit(1)


if __name__ == "__main__":
    main()
