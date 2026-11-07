"""Shared helpers for the Phase 1 smoke scripts. Only fields documented in CLAUDE.md are used.

The API key is read from .env through backend/app/config.py and is never printed.
"""
from __future__ import annotations

import asyncio
import io
import json
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
import time
import warnings
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config import get_settings  # noqa: E402

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import audioop  # stdlib in Python 3.11 (removed in 3.13)

REST_BASE = "https://api.vachana.ai"
WS_BASE = "wss://api.vachana.ai"
PRISMA_MODEL = "prisma-v3.0"
FRAME_BYTES = 1024          # PCM16 mono 16 kHz -> 512 samples = 32 ms
FRAME_SECONDS = 0.032
MAX_REST_SECONDS = 30.0

FINANCE_TERMS = [
    "guaranteed", "returns", "ULIP", "endowment", "lock-in", "surrender charge", "maturity",
    "premium paying term", "policy term", "sum assured", "fund value", "NAV", "free look",
    "bonus", "FD", "fixed deposit", "tax free", "80C", "mortality charge", "Suraksha Plus",
    "Bharosa Life",
]


def api_key() -> str:
    key = get_settings().gnani_api_key
    if key is None or not key.get_secret_value().strip():
        sys.exit("GNANI_API_KEY is not set in .env")
    return key.get_secret_value().strip()


def rest_headers() -> dict[str, str]:
    return {"X-API-Key-ID": api_key()}


def wav_duration(data: bytes) -> float:
    from app.gnani import fix_wav_header  # Timbre sends 0xFFFFFFFF streaming sizes
    with wave.open(io.BytesIO(fix_wav_header(data))) as w:
        return w.getnframes() / float(w.getframerate())


def wav_to_pcm16_mono_16k(path: Path) -> bytes:
    """Read any PCM WAV and return raw PCM16 mono 16 kHz bytes."""
    with wave.open(str(path)) as w:
        channels, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
        pcm = w.readframes(w.getnframes())
    if width != 2:
        pcm = audioop.lin2lin(pcm, width, 2)
    if channels == 2:
        pcm = audioop.tomono(pcm, 2, 0.5, 0.5)
    elif channels != 1:
        sys.exit(f"{path}: {channels} channels not supported; convert to mono first")
    if rate != 16000:
        pcm, _ = audioop.ratecv(pcm, 2, 1, rate, 16000, None)
    return pcm


def error_code(resp) -> str:
    """Best-effort error code from a Gnani error body (never includes the key)."""
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:200]
    if isinstance(body, dict):
        for k in ("error_code", "code", "error"):
            v = body.get(k)
            if isinstance(v, str):
                return v
            if isinstance(v, dict) and isinstance(v.get("code"), str):
                return v["code"]
    return json.dumps(body)[:200]


def stream_headers(lang: str, fmt: str, keyterms: list[str] | None, idle_timeout: int = 60) -> dict:
    h = {
        "x-api-key-id": api_key(),
        "model": PRISMA_MODEL,
        "language_code": lang,
        "x-sample-rate": "16000",
        "format": fmt,
        "x-idle-timeout-sec": str(idle_timeout),
    }
    if keyterms:
        h["keyterms"] = json.dumps(keyterms)
    return h


async def stream_pcm(pcm: bytes, lang: str, fmt: str, keyterms: list[str] | None,
                     on_connected=None, verbose: bool = True) -> dict:
    """Stream PCM16 mono 16 kHz through Prisma streaming. Returns a result dict.

    on_connected: optional coroutine function started (as a task) once the server says 'connected'.
    """
    import websockets

    result = {"types": [], "transcripts": [], "errors": [], "side_task": None,
              "first_transcript_s": None, "frames": 0}
    try:
        return await _stream(websockets, pcm, lang, fmt, keyterms, on_connected, verbose, result)
    except websockets.exceptions.InvalidStatus as e:
        status = e.response.status_code
        body = e.response.body.decode("utf-8", "replace")[:200] if e.response.body else ""
        print(f"  handshake rejected: HTTP {status} {body}")
        result["errors"].append({"handshake_status": status, "body": body})
        if on_connected is not None:  # still run the side call so the probe gets an answer
            result["side_result"] = await on_connected()
        return result


async def _stream(websockets, pcm, lang, fmt, keyterms, on_connected, verbose, result) -> dict:
    url = f"{WS_BASE}/stt/v3/stream"
    t0 = time.perf_counter()
    connected = asyncio.Event()

    async with websockets.connect(url, additional_headers=stream_headers(lang, fmt, keyterms),
                                  max_size=None) as ws:

        async def receiver():
            async for raw in ws:
                if isinstance(raw, bytes):
                    if verbose:
                        print(f"  [{time.perf_counter() - t0:6.2f}s] <binary {len(raw)} bytes>")
                    continue
                try:
                    msg = json.loads(raw)
                except ValueError:
                    print(f"  non-JSON message: {raw[:200]}")
                    continue
                mtype = msg.get("type", "?")
                result["types"].append(mtype)
                stamp = f"[{time.perf_counter() - t0:6.2f}s]"
                if mtype == "connected":
                    connected.set()
                    if verbose:
                        print(f"  {stamp} connected")
                elif mtype == "transcript":
                    if result["first_transcript_s"] is None:
                        result["first_transcript_s"] = time.perf_counter() - t0
                    result["transcripts"].append(msg)
                    if verbose:
                        print(f"  {stamp} transcript #{msg.get('segment_index')} "
                              f"[{msg.get('detected_language_code')}] latency={msg.get('latency')}: "
                              f"{msg.get('text')}")
                elif mtype == "error":
                    result["errors"].append(msg)
                    print(f"  {stamp} ERROR: {json.dumps(msg, ensure_ascii=False)}")
                elif verbose:
                    print(f"  {stamp} {mtype}")

        recv_task = asyncio.create_task(receiver())
        try:
            await asyncio.wait_for(connected.wait(), timeout=10)
        except asyncio.TimeoutError:
            print("  no 'connected' message within 10 s; sending audio anyway")
        if on_connected is not None:
            result["side_task"] = asyncio.create_task(on_connected())

        # pace exactly one 1024-byte frame every 32 ms against a monotonic clock
        n_frames = len(pcm) // FRAME_BYTES
        tail = pcm[n_frames * FRAME_BYTES:]
        start = time.perf_counter()
        try:
            for i in range(n_frames):
                await ws.send(pcm[i * FRAME_BYTES:(i + 1) * FRAME_BYTES])
                delay = start + (i + 1) * FRAME_SECONDS - time.perf_counter()
                if delay > 0:
                    await asyncio.sleep(delay)
            # final partial frame padded with silence so every frame is exactly 1024 bytes
            if tail:
                await ws.send(tail + b"\x00" * (FRAME_BYTES - len(tail)))
            await ws.send(json.dumps({"type": "commit"}))
        except websockets.exceptions.ConnectionClosed as e:
            code = e.rcvd.code if e.rcvd else None
            print(f"  server closed the stream while audio was being sent (code {code})")
            result["errors"].append({"close": code})
            await asyncio.gather(recv_task, return_exceptions=True)
            if result["side_task"] is not None:
                result["side_result"] = await result["side_task"]
            return result
        if verbose:
            print(f"  [{time.perf_counter() - t0:6.2f}s] sent {n_frames + bool(tail)} frames + commit")

        # wait for the server to finish (it may close the socket itself)
        try:
            await asyncio.wait_for(recv_task, timeout=10)
        except asyncio.TimeoutError:
            recv_task.cancel()
        except Exception as e:  # connection closed with an error code
            result["errors"].append({"close": repr(e)})
            print(f"  connection closed: {e!r}")
        result["frames"] = n_frames + bool(tail)
        if result["side_task"] is not None:
            result["side_result"] = await result["side_task"]
    return result
