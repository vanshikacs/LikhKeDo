"""Build the seeded demo cases in demo/cache/<slug>/ from a REAL pipeline run, so /api/demo/<slug> works
when Evon or Gnani is offline. There is no preview mode: every saved case comes from real model calls.

Needs Evon (EVON_BASE_URL/EVON_API_KEY) and spends Gnani credits (Prisma for recorded WAVs, Timbre audio):
  backend/.venv/Scripts/python scripts/seed_demo.py [--slug hi_hinglish] [--no-audio]
Uses demo/pitches/<slug>.wav through Prisma REST if present, else the pitch text.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import db, gnani, pipeline  # noqa: E402
from app.ingest import parse_pdf  # noqa: E402
from app.langs import get_lang  # noqa: E402
from app.evon import evon_health  # noqa: E402
from app.report import build_report  # noqa: E402
from app.routes.cases import _speak_text  # noqa: E402

TITLES = {"hi_hinglish": "Hindi / Hinglish pitch", "ta_tamil_english": "Tamil + English pitch",
          "mr_marathi": "Marathi pitch"}
PRODUCT = "Bharosa Life · Suraksha Plus Guaranteed Wealth Plan"


async def live(pitch: dict, pdf: bytes, clauses, with_audio: bool, out: Path) -> dict:
    lang = get_lang(pitch["lang"])
    with db.session() as s:
        case = db.Case(lang=lang.code, mode="recall", consent=True, product_label=PRODUCT)
        s.add(case)
        s.commit()
        cid = case.id
        for c in clauses:
            s.add(db.ClauseRow(id=c.id, case_id=cid, page=c.page, section=c.section, text=c.text))
        s.commit()
    wav = ROOT / "demo" / "pitches" / f"{pitch['slug']}.wav"
    client = gnani.get_client()
    if wav.exists():
        tr = await client.transcribe_rest(wav.read_bytes(), wav.name, lang.prisma, keyterms=gnani.FINANCE_TERMS,
                                          case_id=cid)
        text, source, rid = tr.text, "rest", (tr.request_ids or [None])[0]
        print(f"  transcribed {wav.name}: {tr.seconds}s, request_ids={tr.request_ids}")
    else:
        text, source, rid = (ROOT / pitch["file"]).read_text(encoding="utf-8"), "text", None
        print("  no WAV found; using the pitch text")
    with db.session() as s:
        s.add(db.Segment(case_id=cid, idx=0, text=text, source=source, prisma_request_id=rid))
        s.commit()
    await pipeline.analyze(cid)
    rep = build_report(cid)
    if rep["status"] != "done":
        raise SystemExit(f"  pipeline failed: {rep['error']}")
    audio, timbre = {}, []
    if with_audio:
        for c in [{"id": "summary"}] + rep["claims"]:
            name = c["id"]
            data, meta = await client.synthesize(_speak_text(rep, name), lang.tts, case_id=cid)
            (out / f"{name}.wav").write_bytes(data)
            audio[name] = f"{name}.wav"
            timbre.append({"target": name, "model": meta["model"], "voice": meta["voice"],
                           "request_ids": meta["request_ids"], "cached": meta["cached"],
                           "latency_ms": meta["latency_ms"]})
            print(f"  audio {name}.wav ({meta['model']}/{meta['voice']}, {meta['latency_ms']} ms, "
                  f"request_ids={meta['request_ids']}{', cache hit' if meta['cached'] else ''})")
        with db.session() as s:
            case = s.get(db.Case, cid)
            case.trace = {**(case.trace or {}), "timbre": timbre}
            s.add(case)
            s.commit()
    rep = {**build_report(cid), "audio": audio}
    rep["_prisma_request_ids"] = [rid] if rid else []
    db.delete_case(cid)
    return rep


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--no-audio", action="store_true")
    a = ap.parse_args()
    key = json.loads((ROOT / "demo/answer_key.json").read_text(encoding="utf-8"))
    pdf = (ROOT / key["document"]).read_bytes()
    clauses = parse_pdf(pdf)
    db.init_db()
    ok, reason = await evon_health()
    if not ok:
        raise SystemExit(f"Evon is not ready ({reason}). Start the GPU server and run scripts/smoke_evon.py first.")
    for pitch in key["pitches"]:
        if a.slug and pitch["slug"] != a.slug:
            continue
        out = ROOT / "demo" / "cache" / pitch["slug"]
        out.mkdir(parents=True, exist_ok=True)
        print(f"{pitch['slug']}:")
        rep = await live(pitch, pdf, clauses, not a.no_audio, out)
        when = datetime.now(timezone.utc).isoformat(timespec="minutes")
        rep["demo"] = {"slug": pitch["slug"], "lang": pitch["lang"], "title": TITLES.get(pitch["slug"], pitch["slug"]),
                       "source": "live", "live_run_at": when, "created": when,
                       "evon_model": rep["trace"]["evon_model"],
                       "prisma_request_ids": rep.pop("_prisma_request_ids")}
        (out / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  wrote {out / 'report.json'} ({rep['demo']['source']})")


if __name__ == "__main__":
    asyncio.run(main())
