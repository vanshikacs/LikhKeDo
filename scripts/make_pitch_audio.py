"""Make synthetic pitch recordings with Gnani Timbre: demo/pitches/<slug>.wav from demo/pitches/<slug>.txt.

Used by /dev/listen "Play pitch audio" (DEBUG_SAVE_AUDIO=true) and by seed_demo.py (Prisma transcribes the WAV,
so the demo cases go through real speech-to-text). Spends Timbre credits; results are cached by text.
  backend/.venv/Scripts/python scripts/make_pitch_audio.py [--slug hi_hinglish]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import db, gnani  # noqa: E402
from app.langs import get_lang  # noqa: E402


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    a = ap.parse_args()
    db.init_db()
    key = json.loads((ROOT / "demo/answer_key.json").read_text(encoding="utf-8"))
    client = gnani.get_client()
    for pitch in key["pitches"]:
        if a.slug and pitch["slug"] != a.slug:
            continue
        text = (ROOT / pitch["file"]).read_text(encoding="utf-8").strip()
        wav, meta = await client.synthesize(text, get_lang(pitch["lang"]).tts)
        out = ROOT / "demo" / "pitches" / f"{pitch['slug']}.wav"
        out.write_bytes(wav)
        secs = (len(wav) - 44) / (2 * int.from_bytes(wav[24:28], "little"))
        print(f"{pitch['slug']}: {out.name} {secs:.1f}s via {meta['model']}/{meta['voice']} "
              f"({meta['latency_ms']} ms, request_ids={meta['request_ids']}{', cache hit' if meta['cached'] else ''})")


if __name__ == "__main__":
    asyncio.run(main())
