"""Seeded demo cases served from demo/cache/<slug>/ (work with Evon and Gnani offline)."""
from __future__ import annotations

import json
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import get_settings

router = APIRouter()
SLUG = re.compile(r"^[a-z0-9_]{1,40}$")
AUDIO = re.compile(r"^[a-z0-9_-]{1,40}\.wav$")


def _dir(slug: str):
    if not SLUG.match(slug):
        raise HTTPException(404, "Demo case not found.")
    d = get_settings().demo_dir / "cache" / slug
    if not (d / "report.json").exists():
        raise HTTPException(404, "Demo case not found. Run scripts/seed_demo.py first.")
    return d


@router.get("/api/demo")
def list_demos() -> list[dict]:
    root = get_settings().demo_dir / "cache"
    out = []
    for p in sorted(root.glob("*/report.json")) if root.exists() else []:
        meta = json.loads(p.read_text(encoding="utf-8")).get("demo", {})
        out.append({"slug": p.parent.name, "lang": meta.get("lang"), "title": meta.get("title")})
    return out


@router.get("/api/demo/{slug}")
def demo_case(slug: str) -> dict:
    return json.loads((_dir(slug) / "report.json").read_text(encoding="utf-8"))


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
    return HTMLResponse(render_slip(json.loads((_dir(slug) / "report.json").read_text(encoding="utf-8"))))
