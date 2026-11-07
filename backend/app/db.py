"""SQLite via sqlmodel. Case data expires after 24 h; a background task purges it."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import JSON, Column, Index, UniqueConstraint
from sqlmodel import Field, Session, SQLModel, create_engine, delete, select

from .config import get_settings

log = logging.getLogger("likhkedo.db")
CASE_TTL = timedelta(hours=24)


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


class Case(SQLModel, table=True):
    __tablename__ = "cases"
    id: str = Field(default_factory=new_id, primary_key=True)
    created_at: datetime = Field(default_factory=now)
    expires_at: datetime = Field(default_factory=lambda: now() + CASE_TTL, index=True)
    lang: str
    mode: str                      # listen | recall
    consent: bool
    status: str = "new"            # new | ready | analyzing | done | error
    product_label: Optional[str] = None
    summary: Optional[str] = None
    error: Optional[str] = None
    trace: dict = Field(default_factory=dict, sa_column=Column(JSON))


class Segment(SQLModel, table=True):
    __tablename__ = "segments"
    __table_args__ = (Index("ix_segments_case_idx", "case_id", "idx"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    case_id: str = Field(foreign_key="cases.id")
    idx: int
    text: str
    detected_lang: Optional[str] = None
    source: str                    # stream | rest | batch | text
    prisma_request_id: Optional[str] = None


class ClauseRow(SQLModel, table=True):
    __tablename__ = "clauses"
    pk: Optional[int] = Field(default=None, primary_key=True)
    id: str                        # e.g. p2-s4 (unique per case)
    case_id: str = Field(foreign_key="cases.id", index=True)
    page: int
    section: str = ""
    text: str


class Claim(SQLModel, table=True):
    __tablename__ = "claims"
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:10], primary_key=True)
    case_id: str = Field(foreign_key="cases.id", index=True)
    segment_id: Optional[int] = None
    idx: int = 0
    quote: str
    claim_en: str
    category: str
    numbers: list = Field(default_factory=list, sa_column=Column(JSON))
    verdict: str                   # WRITTEN | CONTRADICTED | NOT_IN_WRITING
    clause_id: Optional[str] = None
    clause_quote: Optional[str] = None
    clause_page: Optional[int] = None
    explain_en: str = ""
    explain_local: str = ""
    ask_agent: str = ""
    grounded: bool = False
    reason: Optional[str] = None


class TtsCache(SQLModel, table=True):
    __tablename__ = "tts_cache"
    __table_args__ = (UniqueConstraint("hash"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    hash: str
    voice: str
    model: str
    lang: str
    path: str
    chars: int
    created_at: datetime = Field(default_factory=now)


class PrismaCache(SQLModel, table=True):
    __tablename__ = "prisma_cache"
    hash: str = Field(primary_key=True)
    result: dict = Field(sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now)


class ApiCall(SQLModel, table=True):
    __tablename__ = "api_calls"
    id: Optional[int] = Field(default=None, primary_key=True)
    case_id: Optional[str] = Field(default=None, index=True)
    service: str                   # prisma-rest | prisma-stream | timbre | evon
    request_id: Optional[str] = None
    status: Optional[int] = None
    error_code: Optional[str] = None
    latency_ms: int = 0
    units: float = 0               # seconds of audio or characters of text
    created_at: datetime = Field(default_factory=now)


_engine = None


def init_db(url: str | None = None):
    """Create the engine and tables. Tests pass 'sqlite://' for an in-memory database."""
    global _engine
    if url is None:
        data_dir = get_settings().data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{data_dir / 'likhkedo.db'}"
    kwargs = {"connect_args": {"check_same_thread": False}}
    if url == "sqlite://":
        from sqlalchemy.pool import StaticPool
        kwargs["poolclass"] = StaticPool
    _engine = create_engine(url, **kwargs)
    SQLModel.metadata.create_all(_engine)
    return _engine


def engine():
    return _engine if _engine is not None else init_db()


def session() -> Session:
    return Session(engine(), expire_on_commit=False)


def record_call(service: str, *, case_id: str | None = None, request_id: str | None = None,
                status: int | None = None, error_code: str | None = None, latency_ms: int = 0,
                units: float = 0) -> None:
    with session() as s:
        s.add(ApiCall(service=service, case_id=case_id, request_id=request_id, status=status,
                      error_code=error_code, latency_ms=latency_ms, units=units))
        s.commit()
    log.info("gnani_call service=%s request_id=%s status=%s error=%s latency_ms=%s",
             service, request_id, status, error_code, latency_ms)


def delete_case(case_id: str) -> bool:
    with session() as s:
        if s.get(Case, case_id) is None:
            return False
        for model in (Claim, ClauseRow, Segment):
            s.exec(delete(model).where(model.case_id == case_id))
        s.exec(delete(Case).where(Case.id == case_id))
        s.commit()
    return True


def purge_expired() -> int:
    """Delete expired cases, and cached transcripts / synthesized audio older than 24 h (they hold case content)."""
    with session() as s:
        ids = list(s.exec(select(Case.id).where(Case.expires_at < now())))
    for cid in ids:
        delete_case(cid)
    cutoff = now() - CASE_TTL
    with session() as s:
        s.exec(delete(PrismaCache).where(PrismaCache.created_at < cutoff))
        old = list(s.exec(select(TtsCache).where(TtsCache.created_at < cutoff)))
        for row in old:
            try:
                Path(row.path).unlink(missing_ok=True)
            except OSError:
                log.warning("could not delete cached audio %s", Path(row.path).name)
            s.delete(row)
        s.commit()
    return len(ids)


async def purge_loop(interval_s: int = 600) -> None:
    while True:
        try:
            n = purge_expired()
            if n:
                log.info("purged %d expired cases", n)
        except Exception:  # keep the loop alive
            log.exception("purge failed")
        await asyncio.sleep(interval_s)
