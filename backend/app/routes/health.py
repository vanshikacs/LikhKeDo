"""GET /api/health: Gnani reachability, Evon reachability, queue length, demo mode."""
from __future__ import annotations

import time

import httpx
from fastapi import APIRouter

from .. import gnani
from ..config import get_settings
from ..evon import evon_health

router = APIRouter()
_cache: dict[str, tuple[float, bool]] = {}


async def _cached(name: str, ttl: float, probe) -> bool:
    hit = _cache.get(name)
    if hit and time.monotonic() - hit[0] < ttl:
        return hit[1]
    ok = await probe()
    _cache[name] = (time.monotonic(), ok)
    return ok


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


async def evon_up() -> bool:
    return await _cached("evon", 30, evon_health)


@router.get("/api/health")
async def health() -> dict:
    st = get_settings()
    g = await _cached("gnani", 60, _gnani_probe)
    e = await evon_up()
    return {"ok": True, "gnani": "ok" if g else "error", "evon": "ok" if e else "down",
            "queue": gnani.gate.queue, "demo_only": st.demo_only}
