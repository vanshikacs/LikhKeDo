"""GET /api/health: Gnani reachability, Evon reachability, queue length, demo mode."""
from __future__ import annotations

import time

import httpx
from fastapi import APIRouter

from .. import gnani
from ..config import get_settings
from ..evon import evon_health

router = APIRouter()
_cache: dict[str, tuple[float, object]] = {}


async def _cached(name: str, ttl: float, probe):
    hit = _cache.get(name)
    if hit and time.monotonic() - hit[0] < ttl:
        return hit[1]
    val = await probe()
    _cache[name] = (time.monotonic(), val)
    return val


async def _gnani_probe() -> bool:
    """Reachability only (no credits spent): any HTTP answer from the API host counts."""
    if get_settings().gnani_api_key is None:
        return False
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            await c.get(gnani.REST_BASE)
        return True
    except httpx.HTTPError:
        return False


async def evon_status() -> tuple[bool, str]:
    """(ok, reason); cached 30 s when up, 10 s when down so a fresh GPU shows up quickly."""
    hit = _cache.get("evon")
    if hit and time.monotonic() - hit[0] < (30 if hit[1][0] else 10):
        return hit[1]
    val = await evon_health()
    _cache["evon"] = (time.monotonic(), val)
    return val


async def evon_up() -> bool:
    return (await evon_status())[0]


@router.get("/api/health")
async def health() -> dict:
    st = get_settings()
    g = await _cached("gnani", 60, _gnani_probe)
    e, reason = await evon_status()
    return {"ok": True, "gnani": "ok" if g else "error", "evon": "ok" if e else "down", "evon_reason": reason,
            "evon_model": st.evon_model, "evon_provider": st.evon_provider, "evon_label": st.evon_display_label, "queue": gnani.gate.queue, "demo_only": st.demo_only}
