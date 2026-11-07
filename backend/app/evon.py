"""OpenAI-compatible client for the self-hosted Evon v3.3. No other LLM is ever called."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from . import db
from .config import get_settings

log = logging.getLogger("likhkedo.evon")
T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")
_THINK = re.compile(r"<think>.*?</think>", re.S)
_ONE_AT_A_TIME = asyncio.Lock()  # llama-server runs with -np 1: never send two requests at once


class EvonUnavailable(RuntimeError):
    """Evon is not configured or not reachable."""


class EvonJSONError(RuntimeError):
    """Evon returned output that failed validation even after one repair retry."""


def engine_info() -> dict:
    """What produced a report: shown in the UI badge and the trace (never contains keys or URLs)."""
    st = get_settings()
    return {"provider": st.evon_provider, "label": st.evon_display_label, "quant": st.evon_quant,
            "model": None if st.evon_provider == "none" else st.evon_model}


def strip_fences(s: str) -> str:
    s = (s or "").strip()
    s = _FENCE.sub("", s).strip()
    if not s.startswith("{"):  # tolerate a sentence before/after the JSON object
        a, b = s.find("{"), s.rfind("}")
        if a != -1 and b > a:
            s = s[a:b + 1]
    return s


class EvonClient:
    def __init__(self, openai_client=None):
        self._client = openai_client
        st = get_settings()
        self.model = st.evon_model
        self.provider = st.evon_provider
        self.label = st.evon_display_label
        self.calls: list[dict] = []   # trace: latency per call

    def _get(self):
        if self._client is None:
            from openai import AsyncOpenAI
            st = get_settings()
            try:
                base = st.require("evon_base_url")
                key = st.require("evon_api_key").get_secret_value()
            except RuntimeError as e:
                raise EvonUnavailable(str(e)) from None
            self._client = AsyncOpenAI(base_url=base, api_key=key, timeout=st.evon_timeout, max_retries=0)
        return self._client

    async def _complete(self, messages: list[dict], thinking: bool, max_tokens: int, case_id: str | None) -> str:
        if self.provider == "llamacpp":
            async with _ONE_AT_A_TIME:
                # thinking off for every call on the 4-bit build (time limit); prompts ask for JSON only
                return await self._complete_once(messages, False, max_tokens, case_id)
        return await self._complete_once(messages, thinking, max_tokens, case_id)

    async def _complete_once(self, messages: list[dict], thinking: bool, max_tokens: int,
                             case_id: str | None) -> str:
        from openai import APIConnectionError, APITimeoutError, APIStatusError

        client = self._get()
        last = None
        for attempt in range(2):  # one retry on network error
            t0 = time.perf_counter()
            try:
                r = await client.chat.completions.create(
                    model=self.model, messages=messages, temperature=0.6, top_p=0.95, max_tokens=max_tokens,
                    extra_body={"chat_template_kwargs": {"enable_thinking": thinking}})
            except (APIConnectionError, APITimeoutError) as e:
                last = e
                db.record_call("evon", case_id=case_id, error_code=e.__class__.__name__,
                               latency_ms=int((time.perf_counter() - t0) * 1000))
                continue
            except APIStatusError as e:
                db.record_call("evon", case_id=case_id, status=e.status_code, error_code="HTTP_ERROR",
                               latency_ms=int((time.perf_counter() - t0) * 1000))
                raise EvonUnavailable(f"Evon returned HTTP {e.status_code}") from None
            ms = int((time.perf_counter() - t0) * 1000)
            tokens = getattr(getattr(r, "usage", None), "completion_tokens", 0) or 0
            db.record_call("evon", case_id=case_id, request_id=getattr(r, "id", None), status=200,
                           latency_ms=ms, units=tokens)
            self.calls.append({"model": self.model, "provider": self.provider, "thinking": thinking,
                               "latency_ms": ms, "tokens": tokens, "request_id": getattr(r, "id", None)})
            # only content; reasoning is never used (and stripped if a template leaks it into content)
            return _THINK.sub("", r.choices[0].message.content or "").strip()
        raise EvonUnavailable(f"Evon not reachable ({last.__class__.__name__})")

    async def chat_json(self, messages: list[dict], thinking: bool, max_tokens: int, schema: type[T],
                        case_id: str | None = None) -> T:
        content = await self._complete(messages, thinking, max_tokens, case_id)
        try:
            return schema.model_validate(json.loads(strip_fences(content)))
        except (ValueError, ValidationError) as e:
            err = str(e)[:600]
        repair = messages + [
            {"role": "assistant", "content": content[:4000]},
            {"role": "user", "content": f"That was not valid JSON for the required schema. Error: {err}\n"
                                        "Return ONLY the corrected JSON object, nothing else."}]
        content = await self._complete(repair, thinking, max_tokens, case_id)
        try:
            return schema.model_validate(json.loads(strip_fences(content)))
        except (ValueError, ValidationError) as e:
            raise EvonJSONError(str(e)[:300]) from None


# Reason codes for /api/health and the UI banner (never contain the key or the URL).
EVON_REASONS = ("ok", "provider_none", "not_configured", "unreachable", "bad_key", "bad_url", "model_missing", "http_error")


async def evon_health() -> tuple[bool, str]:
    """Probe GET {EVON_BASE_URL}/models. Returns (ok, reason) where reason is one of EVON_REASONS."""
    st = get_settings()
    if st.evon_provider == "none":
        return False, "provider_none"
    if not st.evon_base_url or "<" in st.evon_base_url or st.evon_api_key is None:
        return False, "not_configured"
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(st.evon_base_url.rstrip("/") + "/models",
                            headers={"Authorization": f"Bearer {st.evon_api_key.get_secret_value()}"})
    except httpx.HTTPError:
        return False, "unreachable"
    if r.status_code in (401, 403):
        return False, "bad_key"
    if r.status_code == 404:
        return False, "bad_url"
    if r.status_code != 200:
        return False, "http_error"
    try:
        ids = [m.get("id") for m in r.json().get("data", [])]
    except (ValueError, AttributeError):
        return False, "bad_url"
    if st.evon_model not in ids:
        return False, "model_missing"
    return True, "ok"
