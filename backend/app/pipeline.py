"""extract -> retrieve -> verify -> ground-check -> script check -> summary."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Callable

from rapidfuzz import fuzz
from sqlmodel import select

from . import db, localtext, prompts
from .evon import EvonClient, EvonJSONError, EvonUnavailable
from .ingest import Clause, ClauseIndex, full_text, normalise
from .langs import Lang, get_lang, script_ratio
from .schemas import Extraction, ExtractedClaim, LocalText, Verification

log = logging.getLogger("likhkedo.pipeline")

MATCH_MIN = 90
VERIFY_CONCURRENCY = 4
SCRIPT_MIN = 0.5

# ---------- progress bus (in memory, per case) ----------

PROGRESS: dict[str, list[dict]] = {}
_WAKE: dict[str, asyncio.Event] = {}


def emit(case_id: str, event: dict) -> None:
    PROGRESS.setdefault(case_id, []).append(event)
    ev = _WAKE.get(case_id)
    if ev is not None:
        ev.set()


def waker(case_id: str) -> asyncio.Event:
    return _WAKE.setdefault(case_id, asyncio.Event())


# ---------- grounding check (code, not model) ----------

_MULT = {"lakh": 100_000, "lac": 100_000, "lakhs": 100_000, "लाख": 100_000, "லட்சம்": 100_000,
         "crore": 10_000_000, "करोड़": 10_000_000, "கோடி": 10_000_000, "hazar": 1000, "हज़ार": 1000,
         "thousand": 1000}
_NUM = re.compile(r"\d+(?:\.\d+)?")


def _num_values(text: str) -> set[float]:
    """All numeric values in a normalised string, with lakh/crore expanded."""
    t = normalise(text)
    vals: set[float] = set()
    for m in _NUM.finditer(t):
        v = float(m.group())
        vals.add(v)
        nxt = t[m.end():m.end() + 12].strip().split(" ")[0] if m.end() < len(t) else ""
        if nxt in _MULT:
            vals.add(v * _MULT[nxt])
    return vals


def numbers_in_clause(numbers: list[str], clause_text: str) -> tuple[bool, str | None]:
    have = _num_values(clause_text)
    for n in numbers:
        want = _num_values(n)
        if not want or not (want & have):
            return False, "number_missing"
    return True, None


def fuzzy_in(needle: str, hay: str) -> float:
    a, b = normalise(needle), normalise(hay)
    if not a or not b:
        return 0.0
    return fuzz.partial_ratio(a, b)


@dataclass
class ClaimResult:
    idx: int
    quote: str
    claim_en: str
    category: str
    numbers: list[str]
    verdict: str
    clause_id: str | None = None
    clause_quote: str | None = None
    clause_page: int | None = None
    explain_en: str = ""
    explain_local: str = ""
    ask_agent: str = ""
    grounded: bool = False
    reason: str | None = None
    model_verdict: str | None = None


def ground_check(claim: ExtractedClaim, v: Verification | None, transcript: str,
                 clauses: list[Clause]) -> tuple[str, bool, str | None, Clause | None]:
    """Return (verdict, grounded, reason, clause). Failing checks downgrade to NOT_IN_WRITING."""
    if fuzzy_in(claim.quote, transcript) < MATCH_MIN:
        return "NOT_IN_WRITING", False, "quote_not_in_transcript", None
    if v is None:
        return "NOT_IN_WRITING", False, "invalid_model_output", None
    if v.verdict == "NOT_IN_WRITING":
        return "NOT_IN_WRITING", True, None, None
    if not v.clause_quote:
        return "NOT_IN_WRITING", False, "clause_quote_not_found", None
    by_id = {c.id: c for c in clauses}
    clause = by_id.get(v.clause_id or "")
    if clause is None or fuzzy_in(v.clause_quote, clause.text) < MATCH_MIN:
        # the quote may belong to another clause (wrong id): accept the best exact-enough match
        best = max(clauses, key=lambda c: fuzzy_in(v.clause_quote, c.text), default=None)
        if best is None or fuzzy_in(v.clause_quote, best.text) < MATCH_MIN:
            return "NOT_IN_WRITING", False, "clause_quote_not_found", None
        clause = best
    if v.verdict == "WRITTEN" and claim.numbers:
        ok, why = numbers_in_clause(claim.numbers, clause.text)
        if not ok:
            return "NOT_IN_WRITING", False, why, clause
    return v.verdict, True, None, clause


# ---------- pipeline ----------

@dataclass
class PipelineResult:
    claims: list[ClaimResult]
    summary: str
    trace: dict = field(default_factory=dict)


Progress = Callable[[dict], None]


async def _localize(evon: EvonClient, text: str, lang: Lang, case_id: str | None) -> str | None:
    try:
        out = await evon.chat_json(prompts.localize_messages(text, lang), False, 512, LocalText, case_id)
    except (EvonJSONError, EvonUnavailable):
        return None
    return out.text if script_ratio(out.text, lang) >= SCRIPT_MIN else None


async def run_pipeline(transcript: str, clauses: list[Clause], lang_code: str, evon: EvonClient,
                       progress: Progress = lambda e: None, case_id: str | None = None) -> PipelineResult:
    lang = get_lang(lang_code)
    t_start = time.perf_counter()
    progress({"stage": "extracting"})
    extraction = await evon.chat_json(prompts.extract_messages(transcript, lang), False, 2048, Extraction, case_id)
    claims = extraction.claims
    n = len(claims)
    index = ClauseIndex(clauses)
    cis = full_text(clauses)
    sem = asyncio.Semaphore(VERIFY_CONCURRENCY)
    done = 0

    async def check(i: int, c: ExtractedClaim) -> ClaimResult:
        nonlocal done
        async with sem:
            top = index.search(c.claim_en, k=5) or index.search(c.quote, k=5)
            try:
                v = await evon.chat_json(prompts.verify_messages(c.quote, c.claim_en, c.numbers, cis, top, lang),
                                         True, 4096, Verification, case_id)
            except EvonJSONError:
                v = None
            verdict, grounded, reason, clause = ground_check(c, v, transcript, clauses)
            r = ClaimResult(idx=i, quote=c.quote, claim_en=c.claim_en, category=c.category, numbers=c.numbers,
                            verdict=verdict, grounded=grounded, reason=reason,
                            model_verdict=v.verdict if v else None,
                            explain_en=v.explain_en if v else "", explain_local=v.explain_local if v else "",
                            ask_agent=v.ask_agent if v else "")
            if clause is not None and verdict != "NOT_IN_WRITING":
                r.clause_id, r.clause_quote, r.clause_page = clause.id, v.clause_quote, clause.page
            if verdict != (v.verdict if v else None):
                # never show the model's explanation of a verdict the grounding check overrode
                r.explain_en = localtext.EXPLAIN["en"][verdict]
                r.explain_local = localtext.EXPLAIN[lang.code][verdict]
            if not r.ask_agent:
                r.ask_agent = localtext.ASK[lang.code]
            if lang.code == "en":
                r.explain_local = r.explain_local or r.explain_en
            else:
                # script check on user-facing local text: one stricter rewrite, else the fixed local sentence
                fallback = {"explain_local": localtext.EXPLAIN[lang.code][verdict], "ask_agent": localtext.ASK[lang.code]}
                for attr in ("explain_local", "ask_agent"):
                    val = getattr(r, attr)
                    if val and script_ratio(val, lang) >= SCRIPT_MIN:
                        continue
                    fixed = await _localize(evon, val, lang, case_id) if val else None
                    setattr(r, attr, fixed or fallback[attr])
            done += 1
            progress({"stage": "checking", "i": done, "n": n})
            return r

    results = sorted(await asyncio.gather(*(check(i, c) for i, c in enumerate(claims))), key=lambda r: r.idx)

    progress({"stage": "summarizing"})
    summary = await _summary(evon, results, lang, case_id)
    trace = {"evon_model": evon.model, "evon_calls": list(evon.calls),
             "pipeline_ms": int((time.perf_counter() - t_start) * 1000), "claims": n}
    return PipelineResult(claims=results, summary=summary, trace=trace)


async def _summary(evon: EvonClient, results: list[ClaimResult], lang: Lang, case_id: str | None) -> str:
    if not results:
        return localtext.NO_PROMISES[lang.code]
    # verdict + category only: the summary must not echo English claim text
    payload = [{"verdict": r.verdict, "category": r.category} for r in results]
    for _ in range(2):
        try:
            out = await evon.chat_json(prompts.summary_messages(payload, lang), False, 512, LocalText, case_id)
        except (EvonJSONError, EvonUnavailable):
            break
        if lang.code == "en" or script_ratio(out.text.replace("<pauses>", "").replace("<slow>", ""), lang) >= SCRIPT_MIN:
            return out.text
    return localtext.fallback_summary(lang.code, [(r.verdict, r.category) for r in results])


# ---------- case-level wrapper ----------

async def analyze(case_id: str, evon: EvonClient | None = None) -> None:
    evon = evon or EvonClient()
    PROGRESS[case_id] = []
    with db.session() as s:
        case = s.get(db.Case, case_id)
        segs = list(s.exec(select(db.Segment).where(db.Segment.case_id == case_id).order_by(db.Segment.idx)))
        rows = list(s.exec(select(db.ClauseRow).where(db.ClauseRow.case_id == case_id)))
        case.status = "analyzing"
        s.add(case)
        s.commit()
    clauses = [Clause(id=r.id, page=r.page, section=r.section, text=r.text) for r in rows]
    transcript = "\n".join(s.text for s in segs)
    try:
        result = await run_pipeline(transcript, clauses, case.lang, evon, lambda e: emit(case_id, e), case_id)
    except EvonUnavailable as e:
        _fail(case_id, "EVON_DOWN", str(e))
        return
    except EvonJSONError:
        _fail(case_id, "EVON_BAD_OUTPUT", "The model's answer could not be read. Please try again.")
        return
    except Exception as e:  # never leave a case stuck in 'analyzing'
        # type only: exception messages can quote transcript text, which must never reach logs
        log.error("pipeline failed case=%s error=%s", case_id, e.__class__.__name__)
        _fail(case_id, "PIPELINE_ERROR", "Something went wrong while checking. Please try again.")
        return

    with db.session() as s:
        for r in result.claims:
            d = asdict(r)
            d.pop("model_verdict")
            seg = max(segs, key=lambda x: fuzzy_in(r.quote, x.text), default=None)
            s.add(db.Claim(case_id=case_id, segment_id=seg.id if seg else None, **d))
        case = s.get(db.Case, case_id)
        case.summary = result.summary
        case.status = "done"
        case.trace = {**(case.trace or {}), **result.trace}
        s.add(case)
        s.commit()
    emit(case_id, {"stage": "done"})


def _fail(case_id: str, code: str, message: str) -> None:
    with db.session() as s:
        case = s.get(db.Case, case_id)
        if case is not None:
            case.status, case.error = "error", message
            s.add(case)
            s.commit()
    emit(case_id, {"stage": "error", "code": code, "message": message})
