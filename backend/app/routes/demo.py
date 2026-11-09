"""Seeded demo cases served from demo/cache/<slug>/ (work with Evon and Gnani offline).

Only cases saved from a real pipeline run (scripts/seed_demo.py, metadata demo.live_run_at) are served.
"""
from __future__ import annotations

import json
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import get_settings

router = APIRouter()
SLUG = re.compile(r"^[a-z0-9_]{1,40}$")
AUDIO = re.compile(r"^[a-z0-9_-]{1,40}\.wav$")


# Saved cases kept in the repo for transparency but not served in the public showcase. The Marathi run has two
# wrong "Different on paper" cards (README, "Demo cases"); showing it as an example would mislead.
HELD_BACK = {"mr_marathi"}


def is_live(rep: dict) -> bool:
    meta = rep.get("demo") or {}
    return meta.get("source") == "live" and bool(meta.get("live_run_at"))


def _load(slug: str) -> tuple:
    if not SLUG.match(slug) or slug in HELD_BACK:
        raise HTTPException(404, "Demo case not found.")
    d = get_settings().demo_dir / "cache" / slug
    f = d / "report.json"
    if not f.exists():
        raise HTTPException(404, "Demo case not found. Run scripts/seed_demo.py first.")
    rep = json.loads(f.read_text(encoding="utf-8"))
    if not is_live(rep):
        raise HTTPException(404, "This demo case was not saved from a live run.")
    return d, rep


def _dir(slug: str):
    return _load(slug)[0]


@router.get("/api/demo")
def list_demos() -> list[dict]:
    root = get_settings().demo_dir / "cache"
    out = []
    for p in sorted(root.glob("*/report.json")) if root.exists() else []:
        if p.parent.name in HELD_BACK:
            continue
        rep = json.loads(p.read_text(encoding="utf-8"))
        if not is_live(rep):
            continue
        meta = rep["demo"]
        out.append({"slug": p.parent.name, "lang": meta.get("lang"), "title": meta.get("title"),
                    "live_run_at": meta.get("live_run_at")})
    return out


@router.get("/api/demo/{slug}")
def demo_case(slug: str) -> dict:
    return _load(slug)[1]


@router.get("/api/demo/{slug}/audio/{name}")
def demo_audio(slug: str, name: str):
    if not AUDIO.match(name):
        raise HTTPException(404, "Audio not found.")
    f = _dir(slug) / name
    if not f.exists():
        raise HTTPException(404, "Audio not found.")
    return FileResponse(f, media_type="audio/wav")


@router.get("/api/demo/{slug}/slip")
def demo_slip(slug: str):
    from fastapi.responses import HTMLResponse

    from ..report import render_slip
    return HTMLResponse(render_slip(_load(slug)[1]))


@router.get("/api/dev/pitch/{slug}")
def dev_pitch_audio(slug: str):
    """DEV ONLY (DEBUG_SAVE_AUDIO=true): synthetic pitch audio for /dev/listen and recording the video.
    Files come from scripts/make_pitch_audio.py (Timbre reading demo/pitches/<slug>.txt)."""
    if not get_settings().debug_save_audio or not SLUG.match(slug):
        raise HTTPException(404, "Not found.")
    f = get_settings().demo_dir / "pitches" / f"{slug}.wav"
    if not f.exists():
        raise HTTPException(404, "No pitch audio yet. Run scripts/make_pitch_audio.py.")
    return FileResponse(f, media_type="audio/wav")
