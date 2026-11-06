"""Case API: create, recall, document, analyze (+SSE progress), report, speak, slip, delete."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from pydantic import ValidationError
from sqlmodel import func, select

from .. import db, gnani, pipeline
from ..config import get_settings
from ..evon import EvonClient
from ..ingest import IngestError, parse_pdf
from ..langs import get_lang
from ..report import build_report, render_slip
from ..schemas import CaseCreate, DemoDoc, SpeakRequest
from .health import evon_up

log = logging.getLogger("likhkedo.api")
router = APIRouter(prefix="/api/cases")

MAX_AUDIO_BYTES = 5 * 1024 * 1024
MAX_PDF_BYTES = 5 * 1024 * 1024
MAX_AUDIO_S = 30.0
DEMO_HINT = "Live checking is unavailable right now. Please open the demo case: /api/demo/hi_hinglish"

# Factory so tests can inject a fake Evon client.
evon_factory = EvonClient
_rate: dict[str, deque] = defaultdict(deque)
_tasks: set[asyncio.Task] = set()


def _case(case_id: str) -> db.Case:
    if len(case_id) > 64:
        raise HTTPException(404, "Case not found.")
    with db.session() as s:
        c = s.get(db.Case, case_id)
    if c is None:
        raise HTTPException(404, "Case not found or expired.")
    return c


async def _body(request: Request, limit: int) -> bytes:
    size = int(request.headers.get("content-length") or 0)
    if size > limit:
        raise HTTPException(413, f"File too large (max {limit // (1024 * 1024)} MB).")
    data = await request.body()
    if len(data) > limit:
        raise HTTPException(413, f"File too large (max {limit // (1024 * 1024)} MB).")
    if not data:
        raise HTTPException(400, "Empty upload.")
    return data


def _gnani_http(e: gnani.GnaniError) -> HTTPException:
    status = 503 if e.code in ("NO_CREDIT", "RATE_LIMITED", "UPSTREAM_TIMEOUT", "NO_API_KEY") or (e.http_status or 0) >= 500 else 400
    return HTTPException(status, {"code": e.code, "message": e.friendly, "request_id": e.request_id})


@router.post("")
async def create_case(request: Request) -> dict:
    try:
        body = CaseCreate.model_validate(await request.json())
    except (ValidationError, ValueError) as e:
        raise HTTPException(422, "Send {lang: hi|en|ta|mr, mode: listen|recall, consent: true}.") from e
    with db.session() as s:
        c = db.Case(lang=body.lang, mode=body.mode, consent=body.consent)
        s.add(c)
        s.commit()
    return {"id": c.id, "expires_at": c.expires_at.isoformat()}


@router.post("/{case_id}/recall")
async def recall(case_id: str, request: Request) -> dict:
    case = _case(case_id)
    audio = await _body(request, MAX_AUDIO_BYTES)
    try:
        pcm = gnani.to_pcm16k(audio)
    except gnani.GnaniError as e:
        raise _gnani_http(e) from None
    seconds = len(pcm) / 32000
    if seconds > MAX_AUDIO_S + 0.5:
        raise HTTPException(400, "Recording is too long. Please keep it under 30 seconds.")
    if seconds < 0.5:
        raise HTTPException(400, "The recording is empty. Please try again.")
    lang = get_lang(case.lang)
    with db.session() as s:
        prev = list(s.exec(select(db.Segment.text).where(db.Segment.case_id == case_id).order_by(db.Segment.idx)))
        n = s.exec(select(func.count()).select_from(db.Segment).where(db.Segment.case_id == case_id)).one()
    try:
        tr = await gnani.get_client().transcribe_rest(
            gnani.pcm_to_wav(pcm), "recall.wav", lang.prisma, keyterms=gnani.FINANCE_TERMS,
            topic="A buyer recalls what an insurance or bank salesperson promised about a savings plan.",
            previous_text=" ".join(prev)[-600:] or None, case_id=case_id)
    except gnani.GnaniError as e:
        raise _gnani_http(e) from None
    if not tr.text.strip():
        raise HTTPException(400, "We couldn't hear any words. Please try again, a little louder.")
    with db.session() as s:
        seg = db.Segment(case_id=case_id, idx=n, text=tr.text, detected_lang=tr.detected_language_code,
                         source="rest", prisma_request_id=(tr.request_ids or [None])[0])
        s.add(seg)
        s.commit()
    return {"segment": {"idx": seg.idx, "text": seg.text, "lang": seg.detected_lang},
            "request_ids": tr.request_ids, "latency_ms": tr.latency_ms, "cached": tr.cached}


@router.delete("/{case_id}/segments/{idx}")
def delete_segment(case_id: str, idx: int) -> dict:
    _case(case_id)
    with db.session() as s:
        seg = s.exec(select(db.Segment).where(db.Segment.case_id == case_id, db.Segment.idx == idx)).first()
        if seg is None:
            raise HTTPException(404, "Segment not found.")
        s.delete(seg)
        s.commit()
    return {"deleted": idx}


@router.post("/{case_id}/document")
async def document(case_id: str, request: Request) -> dict:
    _case(case_id)
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("application/json"):
        try:
            DemoDoc.model_validate(await request.json())
        except (ValidationError, ValueError):
            raise HTTPException(422, 'Send {"demo_doc": "suraksha_plus"} or upload a PDF.') from None
        data = (get_settings().demo_dir / "policy" / "bharosa_suraksha_plus_cis.pdf").read_bytes()
        label = "Suraksha Plus Guaranteed Wealth Plan (Bharosa Life, FICTIONAL)"
    else:
        data = await _body(request, MAX_PDF_BYTES)
        if not data.startswith(b"%PDF"):
            raise HTTPException(400, "Please upload a PDF file.")
        label = None
    try:
        clauses = await asyncio.to_thread(parse_pdf, data)
    except IngestError as e:
        raise HTTPException(400, str(e)) from None
    with db.session() as s:
        for old in s.exec(select(db.ClauseRow).where(db.ClauseRow.case_id == case_id)):
            s.delete(old)
        for c in clauses:
            s.add(db.ClauseRow(id=c.id, case_id=case_id, page=c.page, section=c.section, text=c.text))
        case = s.get(db.Case, case_id)
        case.product_label = label or case.product_label or "Uploaded document"
        s.add(case)
        s.commit()
    return {"clauses": len(clauses), "pages": max(c.page for c in clauses), "product_label": label}


def _rate_ok(ip: str) -> bool:
    q, now = _rate[ip], time.monotonic()
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= get_settings().analyses_per_hour:
        return False
    q.append(now)
    return True


@router.post("/{case_id}/analyze")
async def analyze(case_id: str, request: Request):
    case = _case(case_id)
    if get_settings().demo_only or not await evon_up():
        return JSONResponse(status_code=503, content={"detail": {
            "code": "LIVE_UNAVAILABLE", "message": DEMO_HINT, "demo": "/api/demo/hi_hinglish"}})
    if case.status == "analyzing":
        return {"status": "analyzing"}
    with db.session() as s:
        nseg = s.exec(select(func.count()).select_from(db.Segment).where(db.Segment.case_id == case_id)).one()
        ncl = s.exec(select(func.count()).select_from(db.ClauseRow).where(db.ClauseRow.case_id == case_id)).one()
    if not nseg:
        raise HTTPException(400, "Nothing to check yet: record or listen to the pitch first.")
    if not ncl:
        raise HTTPException(400, "Add the policy document first.")
    if not _rate_ok(request.client.host if request.client else "?"):
        raise HTTPException(429, "Limit reached: 3 checks per hour. Please try the demo case.")
    with db.session() as s:
        for old in s.exec(select(db.Claim).where(db.Claim.case_id == case_id)):
            s.delete(old)
        c = s.get(db.Case, case_id)
        c.status, c.error = "analyzing", None
        s.add(c)
        s.commit()
    pipeline.PROGRESS[case_id] = []
    task = asyncio.create_task(pipeline.analyze(case_id, evon_factory()))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {"status": "analyzing"}


@router.get("/{case_id}/progress")
async def progress(case_id: str, request: Request):
    _case(case_id)

    async def stream():
        sent = 0
        wake = pipeline.waker(case_id)
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            events = pipeline.PROGRESS.get(case_id, [])
            while sent < len(events):
                ev = events[sent]
                sent += 1
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                if ev.get("stage") in ("done", "error"):
                    return
            with db.session() as s:
                status = s.get(db.Case, case_id)
            if status is None:
                return
            if status.status in ("done", "error") and sent >= len(pipeline.PROGRESS.get(case_id, [])):
                yield f"data: {json.dumps({'stage': status.status, 'message': status.error})}\n\n"
                return
            if await request.is_disconnected():
                return
            wake.clear()
            try:
                await asyncio.wait_for(wake.wait(), timeout=10)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/{case_id}/report")
def report(case_id: str) -> dict:
    _case(case_id)
    return build_report(case_id)


def _speak_text(rep: dict, target: str) -> str:
    if target == "summary":
        if not rep.get("summary"):
            raise HTTPException(400, "No summary yet.")
        return rep["summary"]
    c = next((c for c in rep["claims"] if c["id"] == target), None)
    if c is None:
        raise HTTPException(404, "Promise not found.")
    if rep["lang"] == "en":
        return f"<slow> {c['explain_en']} <pauses> {c['ask_agent']}".strip()
    return f"<slow> {c['explain_local'] or c['explain_en']} <pauses> {c['ask_agent']}".strip()


@router.post("/{case_id}/speak")
async def speak(case_id: str, request: Request):
    case = _case(case_id)
    try:
        body = SpeakRequest.model_validate(await request.json())
    except (ValidationError, ValueError):
        raise HTTPException(422, 'Send {"target": "summary"} or a promise id.') from None
    text = _speak_text(build_report(case_id), body.target)
    try:
        wav, meta = await gnani.get_client().synthesize(text, get_lang(case.lang).tts, case_id=case_id)
    except gnani.GnaniError as e:
        raise _gnani_http(e) from None
    with db.session() as s:
        c = s.get(db.Case, case_id)
        c.trace = {**(c.trace or {}), "timbre": [*(c.trace or {}).get("timbre", []),
                                                 {"target": body.target, "model": meta["model"],
                                                  "voice": meta["voice"], "request_ids": meta["request_ids"],
                                                  "cached": meta["cached"]}]}
        s.add(c)
        s.commit()
    return Response(wav, media_type="audio/wav",
                    headers={"X-Timbre-Model": meta["model"], "X-Cached": str(meta["cached"]).lower()})


@router.get("/{case_id}/slip", response_class=HTMLResponse)
def slip(case_id: str):
    _case(case_id)
    return HTMLResponse(render_slip(build_report(case_id)))


@router.delete("/{case_id}")
def delete(case_id: str) -> dict:
    if not db.delete_case(case_id):
        raise HTTPException(404, "Case not found or already deleted.")
    pipeline.PROGRESS.pop(case_id, None)
    return {"deleted": True}
