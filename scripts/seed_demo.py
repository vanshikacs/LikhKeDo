"""Build the seeded demo cases in demo/cache/<slug>/ so /api/demo/<slug> works with Evon and Gnani offline.

Live (default; needs Evon, spends Gnani credits for Prisma on recorded WAVs and Timbre audio):
  backend/.venv/Scripts/python scripts/seed_demo.py [--slug hi_hinglish] [--no-audio]
  Uses demo/pitches/<slug>.wav through Prisma if present, else the pitch text.

Preview (no model calls at all; labelled in the UI as NOT a live run):
  backend/.venv/Scripts/python scripts/seed_demo.py --preview
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import db, gnani, pipeline  # noqa: E402
from app.ingest import parse_pdf  # noqa: E402
from app.langs import get_lang  # noqa: E402
from app.prompts import FALLBACK_SUMMARY  # noqa: E402
from app.report import DISCLAIMER, build_report  # noqa: E402

TITLES = {"hi_hinglish": "Hindi / Hinglish pitch", "ta_tamil_english": "Tamil + English pitch",
          "mr_marathi": "Marathi pitch"}
PRODUCT = "Suraksha Plus Guaranteed Wealth Plan (Bharosa Life, FICTIONAL)"


def first_sentence(text: str) -> str:
    text = re.sub(r"^\d+\.\s*", "", text)
    return re.split(r"(?<=[.])\s+(?=[A-Z])", text)[0]


def preview(pitch: dict, clauses) -> dict:
    by_id = {c.id: c for c in clauses}
    text = (ROOT / pitch["file"]).read_text(encoding="utf-8")
    claims = []
    for i, p in enumerate(pitch["promises"]):
        cl = by_id.get(p["expected_clause_id"] or "")
        explain = {"WRITTEN": "The document states this.",
                   "CONTRADICTED": "The document states something different.",
                   "NOT_IN_WRITING": "The document does not mention this. Ask for it in writing."}[p["expected_verdict"]]
        claims.append({"id": p["id"], "quote": p["quote_hint"], "claim_en": p["claim_en"], "category": "other",
                       "numbers": [], "verdict": p["expected_verdict"],
                       "clause_id": cl.id if cl else None, "clause_quote": first_sentence(cl.text) if cl else None,
                       "clause_page": cl.page if cl else None, "explain_en": explain, "explain_local": "",
                       "ask_agent": "Can you give me this in writing?", "grounded": True, "reason": None})
    bad = [c for c in claims if c["verdict"] != "WRITTEN"]
    summary = FALLBACK_SUMMARY[pitch["lang"]].format(n=len(claims), k=len(bad), top=bad[0]["claim_en"])
    counts = {v: sum(1 for c in claims if c["verdict"] == v) for v in ("WRITTEN", "CONTRADICTED", "NOT_IN_WRITING")}
    return {"id": f"demo-{pitch['slug']}", "lang": pitch["lang"], "mode": "recall", "status": "done", "error": None,
            "product_label": PRODUCT, "summary": summary, "counts": counts, "clauses": len(clauses),
            "transcript": [{"idx": 0, "text": text, "source": "text", "lang": None}], "claims": claims,
            "trace": {"prisma_model": None, "evon_model": None, "evon_calls": [], "pipeline_ms": None,
                      "timbre": [], "calls": []},
            "disclaimer": DISCLAIMER}


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
    audio = {}
    if with_audio:
        targets = [("summary", rep["summary"])] + [
            (c["id"], f"<slow> {c['explain_local'] or c['explain_en']} <pauses> {c['ask_agent']}") for c in rep["claims"]]
        for name, txt in targets:
            data, meta = await client.synthesize(txt, lang.tts, case_id=cid)
            (out / f"{name}.wav").write_bytes(data)
            audio[name] = f"{name}.wav"
            print(f"  audio {name}.wav ({meta['model']}/{meta['voice']}, request_ids={meta['request_ids']})")
        rep = {**build_report(cid), "audio": audio}
    db.delete_case(cid)
    return rep


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--no-audio", action="store_true")
    a = ap.parse_args()
    key = json.loads((ROOT / "demo/answer_key.json").read_text(encoding="utf-8"))
    pdf = (ROOT / key["document"]).read_bytes()
    clauses = parse_pdf(pdf)
    if not a.preview:
        db.init_db()
    for pitch in key["pitches"]:
        if a.slug and pitch["slug"] != a.slug:
            continue
        out = ROOT / "demo" / "cache" / pitch["slug"]
        out.mkdir(parents=True, exist_ok=True)
        print(f"{pitch['slug']}:")
        rep = preview(pitch, clauses) if a.preview else await live(pitch, pdf, clauses, not a.no_audio, out)
        rep["demo"] = {"slug": pitch["slug"], "lang": pitch["lang"], "title": TITLES.get(pitch["slug"], pitch["slug"]),
                       "source": "answer_key_preview" if a.preview else "live",
                       "created": datetime.now(timezone.utc).isoformat(timespec="minutes")}
        (out / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  wrote {out / 'report.json'} ({rep['demo']['source']})")


if __name__ == "__main__":
    asyncio.run(main())
