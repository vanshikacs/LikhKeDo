"""Browser WebSocket <-> Prisma v3.0 streaming WebSocket.

Browser protocol:
  -> first text message {"lang": "hi", "sample_rate"?: 48000, "debug_save"?: bool}
  -> optional {"type": "info", "sample_rate": 48000}
  -> binary PCM16 mono 16 kHz frames (re-buffered to exactly 1024 bytes, then paced at 32 ms to Prisma)
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
from collections import Counter
from contextlib import AsyncExitStack

import websockets
from fastapi import WebSocket, WebSocketDisconnect
from sqlmodel import select

from . import db, gnani
from .config import get_settings
from .langs import LANGS, stream_locale
from .redflags import find_redflags

log = logging.getLogger("likhkedo.stream")

WS_URL = f"{gnani.WS_BASE}/stt/v3/stream"
FRAME = 1024
FRAME_S = 0.032
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


def _log_stats(case_id: str, st: dict, frames_out: int) -> None:
    """Audio health per session. Counts and sizes only, never transcript text."""
    span = (st["t_last"] - st["t_first"]) if st["t_first"] and st["t_last"] else 0.0
    secs_in = sum(size * n for size, n in st["sizes"].items()) / 32000
    log.info("stream_stats case=%s browser_sample_rate=%s msgs_in=%d audio_in_s=%.1f over_s=%.1f "
             "msgs_per_s=%.1f msg_sizes=%s frames_out=%d prisma_errors=%d",
             case_id, st["sample_rate"], st["msgs_in"], secs_in, span,
             st["msgs_in"] / span if span else 0.0, dict(st["sizes"].most_common(3)), frames_out,
             st["prisma_errors"])


def _save_debug(pcm: bytes) -> None:
    """DEV ONLY (DEBUG_SAVE_AUDIO=true): the exact 16 kHz stream Prisma received."""
    out = get_settings().data_dir / "debug" / "last_stream.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(gnani.pcm_to_wav(pcm))
    log.info("debug: saved %.1f s of streamed audio to %s", len(pcm) / 32000, out)


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
    lang_code = stream_locale(LANGS[lang] if lang in LANGS else LANGS[case.lang])
    stats = {"sample_rate": first.get("sample_rate"), "msgs_in": 0, "sizes": Counter(),
             "t_first": None, "t_last": None, "prisma_errors": 0}
    save_debug = bool(first.get("debug_save")) and get_settings().debug_save_audio
    debug_pcm = bytearray() if save_debug else None

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

                queue: asyncio.Queue = asyncio.Queue()

                async def browser_to_queue():
                    """Receive browser audio, re-buffer to exact 1024-byte frames, queue them."""
                    buf = b""
                    while True:
                        msg = await ws.receive()
                        if msg["type"] == "websocket.disconnect":
                            raise WebSocketDisconnect(msg.get("code", 1000))
                        if msg.get("bytes"):
                            data = msg["bytes"]
                            now = time.perf_counter()
                            stats["msgs_in"] += 1
                            stats["sizes"][len(data)] += 1
                            stats["t_first"] = stats["t_first"] or now
                            stats["t_last"] = now
                            buf += data
                            while len(buf) >= FRAME:
                                queue.put_nowait(buf[:FRAME])
                                buf = buf[FRAME:]
                        elif msg.get("text"):
                            try:
                                ctl = json.loads(msg["text"])
                            except ValueError:
                                continue
                            if ctl.get("type") == "info" and ctl.get("sample_rate"):
                                stats["sample_rate"] = ctl["sample_rate"]
                            elif ctl.get("type") == "stop":
                                if buf:
                                    queue.put_nowait(buf + bytes(FRAME - len(buf)))
                                queue.put_nowait(None)  # sentinel: commit after the backlog is sent
                                return

                async def queue_to_prisma():
                    """Send frames to Prisma never faster than real time (one per 32 ms), then commit."""
                    nonlocal frames
                    t_start = None
                    while True:
                        frame = await queue.get()
                        if frame is None:
                            await prisma.send(json.dumps({"type": "commit"}))
                            stopped.set()
                            return
                        if t_start is None:
                            t_start = time.perf_counter()
                        ahead = t_start + frames * FRAME_S - time.perf_counter()
                        if ahead > 0:
                            await asyncio.sleep(ahead)
                        await prisma.send(frame)
                        frames += 1
                        if debug_pcm is not None:
                            debug_pcm.extend(frame)

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
                            stats["prisma_errors"] += 1
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

                up = asyncio.create_task(browser_to_queue())
                pump = asyncio.create_task(queue_to_prisma())
                down = asyncio.create_task(prisma_to_browser())
                try:
                    done, _ = await asyncio.wait({up, pump, down}, return_when=asyncio.FIRST_COMPLETED)
                    if up in done and up.exception() is None:
                        # browser said stop: let the paced backlog + commit go out, unless Prisma closes first
                        done, _ = await asyncio.wait({pump, down}, return_when=asyncio.FIRST_COMPLETED)
                    if pump in done and pump.exception() is None and stopped.is_set():
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
                    for t in (up, pump, down):
                        if not t.done():
                            t.cancel()
                    await asyncio.gather(up, pump, down, return_exceptions=True)
                    await _send(ws, {"type": "closed"})
            finally:
                db.record_call("prisma-stream", case_id=case_id, request_id=request_id, status=status_code,
                               error_code=error_code, latency_ms=int((time.perf_counter() - t0) * 1000),
                               units=round(frames * FRAME_S, 2))
                _log_stats(case_id, stats, frames)
                if debug_pcm:
                    _save_debug(bytes(debug_pcm))
    finally:
        try:
            await ws.close()
        except Exception:
            pass
