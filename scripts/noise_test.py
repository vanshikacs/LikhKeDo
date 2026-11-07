"""Noise robustness test (Phase 11): Prisma v2.5 vs v3.0 on noisy and telephone-band pitch recordings.

For each demo/pitches/<slug>.wav (slug must exist in demo/answer_key.json):
  conditions: clean, noise at SNR 20/10/5 dB (noise from demo/noise/*.wav), and 8 kHz telephone band
  (300-3400 Hz band-pass, resampled to 8 kHz and back).
  models: Prisma v2.5 (format verbatim, language hi-IN) and Prisma v3.0 (codemix, "<lang>,en-IN", keyterms).
Then Evon extraction on each transcript; "promise recall" = answer-key promises still extracted.
Writes demo/noise_results.md (and .json). Spends Gnani credits; asks before starting.

NOTE: the v2.5 model name ("prisma-v2.5") is not in CLAUDE.md's documented fields; check docs.gnani.ai
and pass --v25-model if it differs.

Usage: backend/.venv/Scripts/python scripts/noise_test.py [--yes] [--no-evon] [--v25-model prisma-v2.5]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from rapidfuzz import fuzz  # noqa: E402

from app import db, gnani, prompts  # noqa: E402
from app.evon import EvonClient, EvonUnavailable  # noqa: E402
from app.langs import get_lang  # noqa: E402
from app.redflags import find_redflags  # noqa: E402
from app.schemas import Extraction  # noqa: E402

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import audioop

RATE = 16000
CONDITIONS = ["clean", "snr20", "snr10", "snr5", "tel8k"]


def rms(pcm: bytes) -> float:
    return max(1.0, audioop.rms(pcm, 2))


def mix(speech: bytes, noise: bytes, snr_db: float) -> bytes:
    """Add noise (looped to length) scaled so speech/noise RMS ratio = snr_db."""
    if len(noise) < len(speech):
        noise = noise * (len(speech) // len(noise) + 1)
    noise = noise[:len(speech)]
    gain = rms(speech) / (rms(noise) * (10 ** (snr_db / 20)))
    return audioop.add(speech, audioop.mul(noise, 2, gain), 2)


def biquad(pcm: bytes, b, a) -> bytes:
    import array
    x = array.array("h", pcm)
    y = array.array("h", bytes(len(pcm)))
    x1 = x2 = y1 = y2 = 0.0
    b0, b1, b2 = b
    _, a1, a2 = a
    for i, xi in enumerate(x):
        yi = b0 * xi + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, xi, y1, yi
        y[i] = max(-32768, min(32767, int(yi)))
    return y.tobytes()


def coeffs(kind: str, f0: float, q: float = 0.707, fs: float = RATE):
    w = 2 * math.pi * f0 / fs
    al, c = math.sin(w) / (2 * q), math.cos(w)
    if kind == "hp":
        b = ((1 + c) / 2, -(1 + c), (1 + c) / 2)
    else:
        b = ((1 - c) / 2, 1 - c, (1 - c) / 2)
    a0 = 1 + al
    return tuple(v / a0 for v in b), (1.0, -2 * c / a0, (1 - al) / a0)


def telephone(pcm: bytes) -> bytes:
    pcm = biquad(pcm, *coeffs("hp", 300))
    pcm = biquad(pcm, *coeffs("lp", 3400))
    narrow, _ = audioop.ratecv(pcm, 2, 1, RATE, 8000, None)
    back, _ = audioop.ratecv(narrow, 2, 1, 8000, RATE, None)
    return back


def promise_recall(claims, expected) -> int:
    hit = 0
    for e in expected:
        if any(fuzz.token_set_ratio(e["claim_en"].lower(), c.claim_en.lower()) >= 60 for c in claims):
            hit += 1
    return hit


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    ap.add_argument("--no-evon", action="store_true", help="only transcribe and count red flags")
    ap.add_argument("--v25-model", default="prisma-v2.5")
    a = ap.parse_args()

    key = {p["slug"]: p for p in json.loads((ROOT / "demo/answer_key.json").read_text(encoding="utf-8"))["pitches"]}
    pitches = [w for w in sorted((ROOT / "demo/pitches").glob("*.wav")) if w.stem in key]
    noises = sorted((ROOT / "demo/noise").glob("*.wav"))
    if not pitches:
        sys.exit("No recorded pitches: put demo/pitches/<slug>.wav (slug from answer_key.json) first.")
    if not noises:
        sys.exit("No noise clips: put 2-3 WAVs (cafe, traffic, TV) in demo/noise/ first.")
    noise_pcm = [gnani.to_pcm16k(n.read_bytes()) for n in noises]
    models = [("Prisma v2.5", a.v25_model, "verbatim", lambda l: "hi-IN", None),
              ("Prisma v3.0", gnani.PRISMA_MODEL, "codemix", lambda l: get_lang(l).prisma, gnani.FINANCE_TERMS)]

    jobs, calls = [], 0
    for w in pitches:
        pcm = gnani.to_pcm16k(w.read_bytes())
        chunks = 1 if len(pcm) / 32000 <= gnani.MAX_REST_S else len(gnani.split_on_silence(pcm))
        for ci, cond in enumerate(CONDITIONS):
            for m in models:
                jobs.append((w.stem, cond, m, pcm, ci))
                calls += chunks
    print(f"{len(pitches)} pitches x {len(CONDITIONS)} conditions x {len(models)} models = {len(jobs)} transcriptions,"
          f" about {calls} Prisma calls (cached results cost nothing).")
    if not a.yes and input("Proceed? [y/N] ").strip().lower() != "y":
        sys.exit("Cancelled.")

    db.init_db()
    client = gnani.get_client()
    evon = None if a.no_evon else EvonClient()
    results = []
    for slug, cond, (mname, model, fmt, langf, terms), pcm, ci in jobs:
        lang = key[slug]["lang"]
        if cond.startswith("snr"):
            audio = mix(pcm, noise_pcm[ci % len(noise_pcm)], float(cond[3:]))
        elif cond == "tel8k":
            audio = telephone(pcm)
        else:
            audio = pcm
        t0 = time.perf_counter()
        try:
            tr = await client.transcribe_rest(gnani.pcm_to_wav(audio), f"{slug}-{cond}.wav", langf(lang),
                                              keyterms=terms, model=model, fmt=fmt)
            text, err = tr.text, None
        except gnani.GnaniError as e:
            text, err = "", f"{e.code} (HTTP {e.http_status}, request_id={e.request_id})"
        recall = None
        if evon is not None and text:
            try:
                ex = await evon.chat_json(prompts.extract_messages(text, get_lang(lang)), False, 2048, Extraction)
                recall = promise_recall(ex.claims, key[slug]["promises"])
            except EvonUnavailable as e:
                sys.exit(f"Evon unavailable: {e} (use --no-evon to skip extraction)")
            except Exception as e:  # bad JSON after repair: count as 0 recalled
                print(f"  extraction failed: {e.__class__.__name__}")
                recall = 0
        flags = len(find_redflags(text))
        results.append({"pitch": slug, "condition": cond, "model": mname, "recall": recall,
                        "total": len(key[slug]["promises"]), "redflags": flags, "error": err,
                        "transcript": text, "seconds": round(time.perf_counter() - t0, 1)})
        print(f"{slug:18} {cond:6} {mname:12} recall={recall}/{len(key[slug]['promises'])} flags={flags}"
              f"{'  ERROR ' + err if err else ''}")

    (ROOT / "demo/noise_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Noise test", "", f"Run {time.strftime('%Y-%m-%d %H:%M')}. Cells: promises still extracted "
             "(of 6) / red-flag phrases detected, summed over pitches. Synthetic recordings, our own voices.", "",
             "| Model | " + " | ".join(CONDITIONS) + " |", "| --- |" + " --- |" * len(CONDITIONS)]
    for mname in [m[0] for m in models]:
        cells = []
        for cond in CONDITIONS:
            rows = [r for r in results if r["model"] == mname and r["condition"] == cond]
            rec = sum(r["recall"] or 0 for r in rows)
            tot = sum(r["total"] for r in rows)
            fl = sum(r["redflags"] for r in rows)
            cells.append(f"{rec}/{tot} · {fl}" if evon is not None else f"– · {fl}")
        lines.append(f"| {mname} | " + " | ".join(cells) + " |")
    (ROOT / "demo/noise_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\nwrote demo/noise_results.md")


if __name__ == "__main__":
    asyncio.run(main())
