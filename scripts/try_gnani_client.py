"""Phase 3 check: call backend/app/gnani.py on the REAL APIs (spends credits: 1 Prisma + 1 Timbre call).

Usage: backend/.venv/Scripts/python scripts/try_gnani_client.py demo/test_clips/clip1.wav
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import db  # noqa: E402
from app.gnani import FINANCE_TERMS, GnaniError, get_client  # noqa: E402


async def main(wav: Path) -> None:
    db.init_db()
    c = get_client()
    try:
        tr = await c.transcribe_rest(wav.read_bytes(), wav.name, "hi-IN,en-IN", keyterms=FINANCE_TERMS)
        print(f"transcribe_rest: {tr.seconds}s audio, request_ids={tr.request_ids}, cached={tr.cached}, "
              f"lang={tr.detected_language_code}, latency={tr.latency_ms} ms\n  {tr.text}")
        audio, meta = await c.synthesize("<slow> नमस्ते। <pauses> यह LikhKeDo का टेस्ट है।", "hi-IN")
        out = Path("out_client.wav")
        out.write_bytes(audio)
        print(f"synthesize: {len(audio)} bytes -> {out}, meta={meta}")
    except GnaniError as e:
        print(f"GnaniError: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    asyncio.run(main(Path(sys.argv[1])))
