"""Synthetic background noise for scripts/noise_test.py (no recordings of real people; deterministic).

  demo/noise/synthetic_babble.wav  - two other synthetic pitches (Tamil + Marathi, Timbre) talking over each other,
                                     like a crowded branch or a TV in the background
  demo/noise/synthetic_pink.wav    - 30 s of pink noise (fan / traffic hum)

Usage: backend/.venv/Scripts/python scripts/make_noise.py
"""
from __future__ import annotations

import array
import random
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.gnani import pcm_to_wav, to_pcm16k  # noqa: E402

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import audioop

OUT = ROOT / "demo" / "noise"


def babble() -> bytes:
    a = to_pcm16k((ROOT / "demo/pitches/ta_tamil_english.wav").read_bytes())
    b = to_pcm16k((ROOT / "demo/pitches/mr_marathi.wav").read_bytes())
    b = b[len(b) // 3:] + b[:len(b) // 3]  # offset so the two voices don't pause together
    n = min(len(a), len(b))
    return audioop.add(audioop.mul(a[:n], 2, 0.5), audioop.mul(b[:n], 2, 0.5), 2)


def pink(seconds: float = 30.0, rate: int = 16000) -> bytes:
    """Paul Kellet's pink-noise filter over seeded white noise."""
    rnd = random.Random(7)
    b = [0.0] * 7
    out = array.array("h")
    for _ in range(int(seconds * rate)):
        w = rnd.uniform(-1, 1)
        b[0] = 0.99886 * b[0] + w * 0.0555179
        b[1] = 0.99332 * b[1] + w * 0.0750759
        b[2] = 0.96900 * b[2] + w * 0.1538520
        b[3] = 0.86650 * b[3] + w * 0.3104856
        b[4] = 0.55000 * b[4] + w * 0.5329522
        b[5] = -0.7616 * b[5] - w * 0.0168980
        v = sum(b[:6]) + b[6] + w * 0.5362
        b[6] = w * 0.115926
        out.append(max(-32768, min(32767, int(v * 3000))))
    return out.tobytes()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, pcm in (("synthetic_babble.wav", babble()), ("synthetic_pink.wav", pink())):
        (OUT / name).write_bytes(pcm_to_wav(pcm))
        print(f"wrote demo/noise/{name} ({len(pcm) / 32000:.1f} s)")


if __name__ == "__main__":
    main()
