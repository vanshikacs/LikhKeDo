"""Browser WebSocket <-> Prisma v3.0 streaming WebSocket.

Browser protocol:
  -> first text message {"lang": "hi"}   (or "hi-IN")
  -> binary PCM16 mono 16 kHz frames (re-buffered here to exactly 1024 bytes)
  -> {"type": "stop"}
  <- {type: "status", queue}            while waiting for the Gnani lock
  <- {type, text?, segment_index?, detected_language_code?}  forwarded Prisma events
  <- {type: "redflag", phrase, segment_index}
  <- {type: "error", code, message}
  <- {type: "closed"}
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import AsyncExitStack

import websockets
from fastapi import WebSocket, WebSocketDisconnect
from sqlmodel import select

from . import db, gnani
from .config import get_settings
from .langs import LANGS
from .redflags import find_redflags

log = logging.getLogger("likhkedo.stream")

WS_URL = f"{gnani.WS_BASE}/stt/v3/stream"
FRAME = 1024
FINAL_WAIT_S = 5.0
FORWARD_KEYS = ("type", "text", "segment_index", "detected_language_code")


def prisma_headers(lang_code: str) -> dict:
    key = get_settings().gnani_api_key
    return {
        "x-api-key-id": key.get_secret_value().strip() if key else "",
        "model": gnani.PRISMA_MODEL,
        "language_code": lang_code,
        "x-sample-rate": "16000",
        "format": "codemix",
        "keyterms": json.dumps(gnani.FINANCE_TERMS),
        "x-idle-timeout-sec": "120",
    }


def _store_segment(case_id: str, idx: int, text: str, lang: str | None) -> None:
    with db.session() as s:
        row = s.exec(select(db.Segment).where(db.Segment.case_id == case_id, db.Segment.idx == idx,
                                              db.Segment.source == "stream")).first()
        if row is None:
            row = db.Segment(case_id=case_id, idx=idx, text=text, detected_lang=lang, source="stream")
        else:
            row.text, row.detected_lang = text, lang or row.detected_lang
        s.add(row)
        s.commit()


async def _send(ws: WebSocket, msg: dict) -> None:
    try:
        await ws.send_text(json.dumps(msg, ensure_ascii=False))
    except Exception:  # browser already gone
        pass


async def proxy(ws: WebSocket, case_id: str) -> None:
    await ws.accept()
    with db.session() as s:
        case = s.get(db.Case, case_id)
    if case is None:
        await _send(ws, {"type": "error", "code": "NOT_FOUND", "message": "Case not found."})
        await ws.close(code=1008)
        return
    if case.mode == "listen" and not case.consent:
        await _send(ws, {"type": "error", "code": "NO_CONSENT", "message": "Consent is required to listen."})
        await ws.close(code=1008)
        return

    try:
        first = json.loads(await asyncio.wait_for(ws.receive_text(), timeout=10))
        lang = str(first.get("lang") or case.lang).split("-")[0]
    except (asyncio.TimeoutError, ValueError, WebSocketDisconnect):
        await ws.close(code=1008)
        return
    lang_code = LANGS[lang].prisma if lang in LANGS else LANGS[case.lang].prisma

    frames = 0
    request_id: str | None = None
    status_code: int | None = None
    error_code: str | None = None
    t0 = time.perf_counter()
    try:
        async with AsyncExitStack() as stack:
            try:
                if get_settings().stream_holds_lock:
                    if gnani.gate.queue:
                        await _send(ws, {"type": "status", "queue": gnani.gate.queue})
                    await stack.enter_async_context(gnani.gate.slot())
                try:
                    prisma = await stack.enter_async_context(
                        websockets.connect(WS_URL, additional_headers=prisma_headers(lang_code), max_size=None,
                                           open_timeout=10))
                except websockets.exceptions.InvalidStatus as e:
                    status_code = e.response.status_code
                    error_code = {429: "RATE_LIMITED", 402: "NO_CREDIT"}.get(status_code, f"HTTP_{status_code}")
                    await _send(ws, {"type": "error", "code": error_code,
                                     "message": gnani.GnaniError(error_code).friendly})
                    return
                except (OSError, asyncio.TimeoutError) as e:
                    error_code = "CONNECT_FAILED"
                    log.warning("prisma stream connect failed: %s", e.__class__.__name__)
                    await _send(ws, {"type": "error", "code": error_code,
                                     "message": "Could not reach the speech service."})
                    return
                status_code = 101
                stopped = asyncio.Event()
                seg_counter = 0

                async def browser_to_prisma():
                    nonlocal frames
                    buf = b""
                    while True:
                        msg = await ws.receive()
                        if msg["type"] == "websocket.disconnect":
                            raise WebSocketDisconnect(msg.get("code", 1000))
                        if msg.get("bytes"):
                            buf += msg["bytes"]
                            while len(buf) >= FRAME:
                                await prisma.send(buf[:FRAME])
                                buf = buf[FRAME:]
                                frames += 1
                        elif msg.get("text"):
                            try:
                                ctl = json.loads(msg["text"])
                            except ValueError:
                                continue
                            if ctl.get("type") == "stop":
                                if buf:
                                    await prisma.send(buf + b"\x00" * (FRAME - len(buf)))
                                    frames += 1
                                await prisma.send(json.dumps({"type": "commit"}))
                                stopped.set()
                                return

                async def prisma_to_browser():
                    nonlocal request_id, seg_counter, error_code
                    async for raw in prisma:
                        if isinstance(raw, bytes):
                            continue
                        try:
                            ev = json.loads(raw)
                        except ValueError:
                            continue
                        etype = ev.get("type")
                        if etype == "connected":
                            request_id = ev.get("request_id") or request_id
                        if etype == "error":
                            error_code = str(ev.get("code") or ev.get("error_code") or "STREAM_ERROR")
                            await _send(ws, {"type": "error", "code": error_code,
                                             "message": ev.get("message") or "The speech service reported an error."})
                            continue
                        out = {k: ev[k] for k in FORWARD_KEYS if k in ev}
                        await _send(ws, out)
                        if etype == "transcript" and ev.get("text"):
                            idx = ev.get("segment_index")
                            idx = int(idx) if isinstance(idx, int) or (isinstance(idx, str) and idx.isdigit()) else seg_counter
                            seg_counter = max(seg_counter, idx + 1)
                            _store_segment(case_id, idx, ev["text"], ev.get("detected_language_code"))
                            for phrase in find_redflags(ev["text"]):
                                await _send(ws, {"type": "redflag", "phrase": phrase, "segment_index": idx})

                up = asyncio.create_task(browser_to_prisma())
                down = asyncio.create_task(prisma_to_browser())
                try:
                    done, _ = await asyncio.wait({up, down}, return_when=asyncio.FIRST_COMPLETED)
                    if up in done and up.exception() is None and stopped.is_set():
                        # wait up to 5 s for the final transcript, then close
                        try:
                            await asyncio.wait_for(asyncio.shield(down), timeout=FINAL_WAIT_S)
                        except asyncio.TimeoutError:
                            pass
                    elif down in done and down.exception() is not None:
                        exc = down.exception()
                        code = getattr(getattr(exc, "rcvd", None), "code", None)
                        error_code = f"CLOSED_{code}" if code else "STREAM_CLOSED"
                        msg = ("The 15-minute session limit was reached." if code == 1001 else
                               "The speech service rejected the session settings." if code == 1008 else
                               "The speech connection closed.")
                        await _send(ws, {"type": "error", "code": error_code, "message": msg})
                    elif up in done and isinstance(up.exception(), WebSocketDisconnect):
                        log.info("browser disconnected case=%s", case_id)
                finally:
                    for t in (up, down):
                        if not t.done():
                            t.cancel()
                    await asyncio.gather(up, down, return_exceptions=True)
                    await _send(ws, {"type": "closed"})
            finally:
                db.record_call("prisma-stream", case_id=case_id, request_id=request_id, status=status_code,
                               error_code=error_code, latency_ms=int((time.perf_counter() - t0) * 1000),
                               units=round(frames * 0.032, 2))
    finally:
        try:
            await ws.close()
        except Exception:
            pass
