"""All Gnani calls (Prisma REST, Timbre) go through GnaniGate. Fields follow CLAUDE.md only."""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import re
import shutil
import subprocess
import time
import uuid
import warnings
import wave
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from sqlmodel import select

from . import db
from .config import get_settings

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import audioop  # stdlib on Python 3.11

log = logging.getLogger("likhkedo.gnani")

REST_BASE = "https://api.vachana.ai"
WS_BASE = "wss://api.vachana.ai"
PRISMA_MODEL = "prisma-v3.0"
RETRY_STATUSES = {429, 500, 503, 504}
BACKOFF = (0.5, 1.0, 2.0)
MAX_REST_S = 28.0
CHUNK_S = 25.0
TTS_MAX_CHARS = 450

FINANCE_TERMS = [
    "guaranteed", "returns", "ULIP", "endowment", "lock-in", "surrender charge", "maturity",
    "premium paying term", "policy term", "sum assured", "fund value", "NAV", "free look",
    "bonus", "FD", "fixed deposit", "tax free", "80C", "mortality charge", "Suraksha Plus",
    "Bharosa Life",
]

FRIENDLY = {
    "RATE_LIMITED": "The speech service is busy. Please try again in a few seconds.",
    "NO_CREDIT": "The speech service has run out of credit. Please try the demo case.",
    "UPSTREAM_TIMEOUT": "The speech service took too long. Please try again.",
    "EMPTY_AUDIO": "We couldn't hear anything in that recording. Please try again.",
    "UNSUPPORTED_AUDIO_FORMAT": "That audio format isn't supported. Please record again.",
    "MAX_AUDIO_DURATION_EXCEEDED": "That recording is too long. Please keep it under 30 seconds.",
}


class GnaniError(Exception):
    def __init__(self, code: str, http_status: int | None = None, request_id: str | None = None,
                 detail: str = ""):
        self.code, self.http_status, self.request_id, self.detail = code, http_status, request_id, detail
        super().__init__(f"{code} (HTTP {http_status}, request_id={request_id}) {detail}".strip())

    @property
    def friendly(self) -> str:
        return FRIENDLY.get(self.code, "The speech service returned an error. Please try again.")


class GnaniGate:
    """One process-wide lock: the account may allow only ONE active Gnani request at a time."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self.waiting = 0
        self.active = False

    @property
    def queue(self) -> int:
        return self.waiting + (1 if self.active else 0)

    @asynccontextmanager
    async def slot(self):
        self.waiting += 1
        try:
            await self._lock.acquire()
        finally:
            self.waiting -= 1
        self.active = True
        try:
            yield
        finally:
            self.active = False
            self._lock.release()


gate = GnaniGate()


# ---------- audio helpers (in memory only; raw audio never touches disk) ----------

def to_pcm16k(audio: bytes) -> bytes:
    """Any audio -> PCM16 mono 16 kHz. WAV via stdlib; anything else via ffmpeg pipes."""
    if audio[:4] == b"RIFF":
        try:
            with wave.open(io.BytesIO(audio)) as w:
                ch, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
                pcm = w.readframes(w.getnframes())
            if width != 2:
                pcm = audioop.lin2lin(pcm, width, 2)
            if ch == 2:
                pcm = audioop.tomono(pcm, 2, 0.5, 0.5)
            elif ch != 1:
                raise GnaniError("UNSUPPORTED_AUDIO_FORMAT", detail=f"{ch} channels")
            if rate != 16000:
                pcm, _ = audioop.ratecv(pcm, 2, 1, rate, 16000, None)
            return pcm
        except wave.Error:
            pass  # e.g. float WAV: let ffmpeg handle it
    if not shutil.which("ffmpeg"):
        raise GnaniError("UNSUPPORTED_AUDIO_FORMAT", detail="ffmpeg is not installed on the server")
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-ac", "1", "-ar", "16000",
                        "-f", "s16le", "pipe:1"], input=audio, capture_output=True, timeout=60)
    if p.returncode != 0 or not p.stdout:
        raise GnaniError("UNSUPPORTED_AUDIO_FORMAT", detail="could not decode audio")
    return p.stdout


def pcm_to_wav(pcm: bytes, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def split_on_silence(pcm: bytes, max_s: float = CHUNK_S, rate: int = 16000) -> list[bytes]:
    """Split PCM16 mono into chunks <= max_s, cutting at the quietest 50 ms window in the last third."""
    bps = rate * 2
    max_len = int(max_s * bps)
    win = int(0.05 * bps) // 2 * 2
    chunks, start = [], 0
    while len(pcm) - start > max_len:
        lo, hi = start + max_len * 2 // 3, start + max_len
        best, best_rms = hi, None
        for pos in range(lo, hi - win, win):
            r = audioop.rms(pcm[pos:pos + win], 2)
            if best_rms is None or r < best_rms:
                best, best_rms = pos + win // 2, r
        best -= best % 2
        chunks.append(pcm[start:best])
        start = best
    chunks.append(pcm[start:])
    return [c for c in chunks if len(c) >= bps // 10]  # drop < 0.1 s slivers


def fix_wav_header(data: bytes) -> bytes:
    """Timbre returns streaming WAVs whose RIFF/data sizes are 0xFFFFFFFF; patch them to the real sizes."""
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return data
    buf = bytearray(data)
    i = 12
    while i + 8 <= len(buf):
        cid, size = bytes(buf[i:i + 4]), int.from_bytes(buf[i + 4:i + 8], "little")
        if cid == b"data":
            actual = len(buf) - (i + 8)
            if size != actual:
                buf[i + 4:i + 8] = actual.to_bytes(4, "little")
            break
        i += 8 + size + (size & 1)
    buf[4:8] = (len(buf) - 8).to_bytes(4, "little")
    return bytes(buf)


def concat_wavs(parts: list[bytes]) -> bytes:
    if len(parts) == 1:
        return parts[0]
    frames, params = [], None
    for p in parts:
        with wave.open(io.BytesIO(p)) as w:
            params = params or w.getparams()
            frames.append(w.readframes(w.getnframes()))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setparams(params)
        w.writeframes(b"".join(frames))
    return buf.getvalue()


_SENT = re.compile(r"(?<=[.!?।])\s+|(?<=<pauses>)\s*")


def split_text(text: str, max_chars: int = TTS_MAX_CHARS) -> list[str]:
    parts, cur = [], ""
    for s in (x.strip() for x in _SENT.split(text) if x.strip()):
        while len(s) > max_chars:  # one very long sentence: hard split on a space
            cut = s.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            parts.append(s[:cut].strip())
            s = s[cut:].strip()
        if cur and len(cur) + 1 + len(s) > max_chars:
            parts.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        parts.append(cur)
    return parts


# ---------- results ----------

@dataclass
class TranscriptResult:
    text: str
    request_ids: list[str] = field(default_factory=list)
    detected_language_code: str | None = None
    processing_time: float | None = None
    latency_ms: int = 0
    seconds: float = 0.0
    cached: bool = False


def _error_code(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        for k in ("error_code", "code", "error"):
            v = body.get(k)
            if isinstance(v, str) and v:
                return v
            if isinstance(v, dict) and isinstance(v.get("code"), str):
                return v["code"]
    return {429: "RATE_LIMITED", 402: "NO_CREDIT", 504: "UPSTREAM_TIMEOUT"}.get(resp.status_code,
                                                                                f"HTTP_{resp.status_code}")


def _request_id(resp: httpx.Response | None, sent: str) -> str:
    if resp is not None:
        try:
            body = resp.json() if "json" in resp.headers.get("content-type", "") else None
        except ValueError:
            body = None
        if isinstance(body, dict) and body.get("request_id"):
            return str(body["request_id"])
        for h in ("x-request-id", "x-api-request-id"):
            if resp.headers.get(h):
                return resp.headers[h]
    return sent


# ---------- client ----------

class GnaniClient:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, sleep=asyncio.sleep,
                 gate_: GnaniGate | None = None):
        self._transport = transport
        self._sleep = sleep
        self.gate = gate_ or gate

    def _key(self) -> str:
        key = get_settings().gnani_api_key
        if key is None or not key.get_secret_value().strip():
            raise GnaniError("NO_API_KEY", detail="GNANI_API_KEY is not set")
        return key.get_secret_value().strip()

    async def _post(self, service: str, path: str, *, units: float, case_id: str | None,
                    timeout: float = 30.0, **kwargs) -> tuple[httpx.Response, str, int]:
        """POST with the retry policy, under the gate. Returns (response, request_id, latency_ms)."""
        async with self.gate.slot():
            async with httpx.AsyncClient(base_url=REST_BASE, timeout=timeout,
                                         transport=self._transport) as client:
                for attempt in range(len(BACKOFF) + 1):
                    sent_id = f"lkd-{uuid.uuid4().hex[:16]}"
                    headers = {"X-API-Key-ID": self._key(), "X-API-Request-ID": sent_id}
                    t0 = time.perf_counter()
                    resp: httpx.Response | None = None
                    try:
                        resp = await client.post(path, headers=headers, **kwargs)
                        status, code = resp.status_code, (None if resp.status_code == 200 else _error_code(resp))
                    except httpx.TimeoutException:
                        status, code = 504, "UPSTREAM_TIMEOUT"
                    except httpx.TransportError as e:
                        status, code = None, f"NETWORK_{e.__class__.__name__}"
                    ms = int((time.perf_counter() - t0) * 1000)
                    rid = _request_id(resp, sent_id)
                    db.record_call(service, case_id=case_id, request_id=rid, status=status,
                                   error_code=code, latency_ms=ms, units=units)
                    if status == 200:
                        return resp, rid, ms
                    if status in RETRY_STATUSES and attempt < len(BACKOFF):
                        await self._sleep(BACKOFF[attempt])
                        continue
                    raise GnaniError(code or "UNKNOWN", status, rid)
        raise AssertionError("unreachable")

    # ----- Prisma REST -----

    async def transcribe_rest(self, audio: bytes, filename: str, lang_hint: str,
                              keyterms: list[str] | None = None, topic: str | None = None,
                              previous_text: str | None = None, case_id: str | None = None,
                              model: str = PRISMA_MODEL, fmt: str = "codemix") -> TranscriptResult:
        params = {"lang": lang_hint, "keyterms": keyterms, "topic": topic, "prev": previous_text}
        if (model, fmt) != (PRISMA_MODEL, "codemix"):
            params.update(model=model, fmt=fmt)
        key = hashlib.sha256(audio + json.dumps(params, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with db.session() as s:
            hit = s.get(db.PrismaCache, key)
        if hit is not None:
            return TranscriptResult(**{**hit.result, "cached": True})

        pcm = to_pcm16k(audio)
        seconds = len(pcm) / 32000
        if seconds < 0.3:
            raise GnaniError("EMPTY_AUDIO", 400)
        chunks = [pcm] if seconds <= MAX_REST_S else split_on_silence(pcm)

        texts, rids, det, ptime, total_ms = [], [], None, 0.0, 0
        prev = previous_text
        for chunk in chunks:
            data = await self._prisma_once(pcm_to_wav(chunk), filename, lang_hint, keyterms, topic, prev,
                                           case_id, len(chunk) / 32000, model, fmt)
            texts.append(data["transcript"])
            rids.append(data["request_id"])
            det = det or data.get("detected_language_code")
            ptime += float(data.get("processing_time") or 0)
            total_ms += data["_ms"]
            prev = " ".join(texts)[-600:]
        result = TranscriptResult(text=" ".join(t for t in texts if t).strip(), request_ids=rids,
                                  detected_language_code=det, processing_time=round(ptime, 3),
                                  latency_ms=total_ms, seconds=round(seconds, 2))
        with db.session() as s:
            res = {k: v for k, v in result.__dict__.items() if k != "cached"}
            s.merge(db.PrismaCache(hash=key, result=res))
            s.commit()
        return result

    async def _prisma_once(self, wav: bytes, filename, lang, keyterms, topic, prev, case_id, seconds,
                           model: str = PRISMA_MODEL, fmt: str = "codemix") -> dict:
        def form(with_keyterms: bool) -> dict:
            d = {"model": model, "language_code": lang, "format": fmt}
            if with_keyterms and keyterms:
                d["keyterms"] = json.dumps(keyterms[:200], ensure_ascii=False)
            if topic:
                d["topic"] = topic[:1600]
            if prev:
                d["previous_text"] = prev[-600:]
            return d

        try:
            resp, rid, ms = await self._post("prisma-rest", "/stt/v3", units=seconds, case_id=case_id,
                                             data=form(True), files={"audio_file": (filename, wav, "audio/wav")})
        except GnaniError as e:
            if e.code != "INVALID_CONTEXT" or not keyterms:
                raise
            # documented: drop keyterms and retry once
            resp, rid, ms = await self._post("prisma-rest", "/stt/v3", units=seconds, case_id=case_id,
                                             data=form(False), files={"audio_file": (filename, wav, "audio/wav")})
        body = resp.json()
        if not body.get("success", True):
            raise GnaniError(str(body.get("error_code") or "TRANSCRIPTION_FAILED"), resp.status_code, rid)
        return {**body, "request_id": rid, "_ms": ms, "transcript": body.get("transcript") or ""}

    # ----- Timbre -----

    def tts_attempts(self, lang: str, voice: str, model: str) -> list[dict]:
        st = get_settings()
        primary = {"model": model, "voice": voice, "language": lang,
                   "speed": st.tts_speed, "sample_rate": st.tts_sample_rate}
        return [primary,
                {**primary, "speed": None, "sample_rate": 48000},
                {"model": "timbre-v2.5", "voice": "Poorvi", "language": "hi-en", "speed": None,
                 "sample_rate": 48000}]

    async def synthesize(self, text: str, lang: str, voice: str = "Tarika", model: str = "timbre-v3.0",
                         case_id: str | None = None) -> tuple[bytes, dict]:
        """Returns (wav bytes, meta{request_ids, model, voice, cached, latency_ms})."""
        t0 = time.perf_counter()
        key = hashlib.sha256(f"{text}\x00{voice}\x00{model}\x00{lang}".encode()).hexdigest()
        tts_dir = Path(get_settings().data_dir) / "tts"
        with db.session() as s:
            hit = s.exec(select(db.TtsCache).where(db.TtsCache.hash == key)).first()
        if hit is not None and Path(hit.path).exists():
            return Path(hit.path).read_bytes(), {"cached": True, "model": hit.model, "voice": hit.voice,
                                                 "request_ids": [],
                                                 "latency_ms": int((time.perf_counter() - t0) * 1000)}

        attempts = self.tts_attempts(lang, voice, model)
        if lang in ("ta-IN", "mr-IN", "en-IN"):
            attempts = attempts[:2]  # the v2.5 Hindi fallback can't speak these
        parts, rids, used = [], [], None
        for piece in split_text(text):
            last_err = None
            for att in ([used] if used else attempts):
                body = {"text": piece, "voice": att["voice"], "model": att["model"], "language": att["language"],
                        "audio_config": {"sample_rate": att["sample_rate"], "num_channels": 1, "sample_width": 2,
                                         "encoding": "linear_pcm", "container": "wav"}}
                if att["speed"] is not None:
                    body["speed"] = att["speed"]
                try:
                    resp, rid, _ = await self._post("timbre", "/api/v1/tts/inference", units=len(piece),
                                                    case_id=case_id, json=body, timeout=60)
                except GnaniError as e:
                    last_err = e
                    if e.http_status == 400 and not used:
                        continue  # try the next documented combination
                    raise
                used = att
                parts.append(fix_wav_header(resp.content))
                rids.append(rid)
                break
            else:
                raise last_err or GnaniError("TTS_FAILED")
        wav = concat_wavs(parts)
        tts_dir.mkdir(parents=True, exist_ok=True)
        path = tts_dir / f"{key}.wav"
        path.write_bytes(wav)
        with db.session() as s:
            s.add(db.TtsCache(hash=key, voice=voice, model=model, lang=lang, path=str(path), chars=len(text)))
            s.commit()
        return wav, {"cached": False, "model": used["model"], "voice": used["voice"], "request_ids": rids,
                     "latency_ms": int((time.perf_counter() - t0) * 1000)}


_client: GnaniClient | None = None


def get_client() -> GnaniClient:
    global _client
    if _client is None:
        _client = GnaniClient()
    return _client


def set_client(client: GnaniClient | None) -> None:
    """Tests swap in a client with a mock transport."""
    global _client
    _client = client
