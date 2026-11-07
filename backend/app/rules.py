"""Mode B: "Rules check — no AI model". Used only when Evon is not available and the user asks for it.

Plain keyword and number matching against the standard CIS headings. It is deliberately cautious: a promise is
WRITTEN only when its number appears in the matching clause, CONTRADICTED only for a clear clash ("guaranteed"
vs "not guaranteed", or a different number of years/percent in the same heading), and everything else is
NOT_IN_WRITING ("ask for it in writing"). Results still go through the same code-level grounding check.
It is never presented as Evon or as an AI model.
"""
from __future__ import annotations

import re
import time

from . import localtext
from .ingest import Clause
from .langs import get_lang
from .pipeline import ClaimResult, PipelineResult, ground_check
from .schemas import ExtractedClaim, Verification

LABEL = "Rules check — no AI model"
MAX_CLAIMS = 12

_PRODUCT = re.compile(r"suraksha\s+plus(?:\s+guaranteed\s+wealth\s+plan)?|guaranteed\s+wealth\s+plan", re.I)
_SPLIT = re.compile(r"(?<=[।.!?\n])\s*|\n+")

# number words as Prisma codemix writes them (hi / mr / ta / romanised)
_WORDS = {
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पाँच": 5, "पांच": 5, "छह": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
    "बारह": 12, "पंद्रह": 15, "बीस": 20, "पच्चीस": 25, "तीस": 30, "पचास": 50, "सौ": 100,
    "पाच": 5, "सहा": 6, "दहा": 10, "बारा": 12, "पंधरा": 15, "वीस": 20, "तीस": 30,
    "ஒன்று": 1, "இரண்டு": 2, "மூன்று": 3, "நான்கு": 4, "ஐந்து": 5, "ஆறு": 6, "ஏழு": 7, "எட்டு": 8, "பத்து": 10,
    "பன்னிரண்டு": 12, "பதினைந்து": 15, "இருபது": 20, "முப்பது": 30,
    "ek": 1, "do": 2, "teen": 3, "char": 4, "paanch": 5, "panch": 5, "das": 10, "barah": 12, "baarah": 12,
    "pandrah": 15, "bees": 20, "tees": 30,
}
_NUM = r"(\d[\d,]*(?:\.\d+)?|" + "|".join(sorted(map(re.escape, _WORDS), key=len, reverse=True)) + r")"
_UNITS = {
    "years": r"साल|वर्ष[ंे]?|வருஷ\w*|வருட\w*|ஆண்டு\w*|years?|saal",
    "percent": r"percent|प्रतिशत|टक्के|%|சதவீத\w*",
    "days": r"दिन|दिवस\w*|நாள\w*|நாட்கள்|days?|din",
    "lakh": r"लाख\w*|லட்ச\w*|lakhs?|lac",
}
_CLAIM_NUM = re.compile(_NUM + r"\s*(" + "|".join(f"(?P<{u}>{p})" for u, p in _UNITS.items()) + r")", re.I)
_DOC_NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(years?|%|days|lakh)", re.I)
_DOC_RS = re.compile(r"Rs\.?\s*(\d[\d,]*)", re.I)

GUARANTEE = re.compile(r"guarante|गारंटी|गॅरंटी|हमी|உத்தரவாத|கேரண்டி", re.I)
# category -> words in the spoken promise
CATEGORY_WORDS = [
    ("lock_in", re.compile(r"lock[\s-]?in|लॉक", re.I)),
    ("premium_term", re.compile(r"premium|प्रीमियम|பிரீமியம்", re.I)),
    ("liquidity", re.compile(r"\bloan|लोन|कर्ज|withdraw|निकाल", re.I)),
    ("cover", re.compile(r"cover|कवर|sum assured|बीमा राशि", re.I)),
    ("tax", re.compile(r"\btax|टैक्स|टॅक्स|வரி", re.I)),
    ("free_look", re.compile(r"return\s*कर|वापस|लौटा|परत\s*कर|திருப்பி", re.I)),
    ("returns", re.compile(r"return|रिटर्न|percent|प्रतिशत|ब्याज|interest|better|बेहतर|FD", re.I)),
]
# category -> standard CIS headings (IRDAI format) used to find the clause
ANCHORS = {
    "premium_term": re.compile(r"premium pay(?:ing|ment) term", re.I),
    "policy_term": re.compile(r"\bpolicy term\b", re.I),
    "lock_in": re.compile(r"lock-?in", re.I),
    "liquidity": re.compile(r"\bloan\b", re.I),
    "cover": re.compile(r"sum assured|death benefit|life cover", re.I),
    "tax": re.compile(r"\btax\b", re.I),
    "free_look": re.compile(r"free-?look", re.I),
    "returns": re.compile(r"\breturns?\b.*guarantee|guaranteed? returns?", re.I),
}
CONTRADICTABLE = {"premium_term", "policy_term", "lock_in", "free_look", "returns"}
CATEGORY_OUT = {"free_look": "other"}  # schema categories


def _value(tok: str) -> float:
    return float(tok.replace(",", "")) if tok[0].isdigit() else float(_WORDS[tok.lower()] if tok.lower() in _WORDS else _WORDS[tok])


def claim_values(text: str) -> list[tuple[str, float]]:
    out = []
    for m in _CLAIM_NUM.finditer(text):
        unit = next(u for u in _UNITS if m.group(u))
        v = _value(m.group(1))
        out.append(("amount", v * 100_000) if unit == "lakh" else (unit, v))
    return out


def doc_values(text: str) -> list[tuple[str, float]]:
    out = []
    for m in _DOC_NUM.finditer(text):
        u = m.group(2).lower()
        unit = "percent" if u == "%" else "days" if u.startswith("day") else "lakh" if u == "lakh" else "years"
        v = float(m.group(1).replace(",", ""))
        out.append(("amount", v * 100_000) if unit == "lakh" else (unit, v))
    out += [("amount", float(m.group(1).replace(",", ""))) for m in _DOC_RS.finditer(text)]
    return out


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.;:])\s+", text) if s.strip()]


def _clause_sentence(clause: Clause, pred) -> str:
    return next((s for s in _sentences(clause.text) if pred(s)), _sentences(clause.text)[0])


def _anchor(clauses: list[Clause], category: str) -> Clause | None:
    pat = ANCHORS.get(category)
    if pat is None:
        return None
    hits = [(m.start(), c) for c in clauses if (m := pat.search(c.text))]
    return min(hits, key=lambda h: h[0])[1] if hits else None


def _category(sentence: str) -> str:
    plain = _PRODUCT.sub(" ", sentence)
    if GUARANTEE.search(plain):
        return "returns"
    return next((cat for cat, pat in CATEGORY_WORDS if pat.search(plain)), "other")


def extract(transcript: str) -> list[tuple[str, str]]:
    """(sentence, category) for sentences that make a checkable promise: a number with a unit, or a finance keyword."""
    out = []
    for s in _SPLIT.split(transcript):
        s = s.strip(" ,")
        if len(s.split()) < 3:
            continue
        cat = _category(s)
        if cat == "other" and not claim_values(s):
            continue
        out.append((s, cat))
    return out[:MAX_CLAIMS]


def judge(sentence: str, category: str, clauses: list[Clause]) -> Verification:
    plain = _PRODUCT.sub(" ", sentence)
    if GUARANTEE.search(plain):
        not_g = next((c for c in clauses if re.search(r"not guaranteed", c.text, re.I)), None)
        if not_g:
            q = _clause_sentence(not_g, lambda s: re.search(r"not guaranteed", s, re.I))
            return Verification(verdict="CONTRADICTED", clause_id=not_g.id, clause_quote=q)
    clause = _anchor(clauses, category)
    said = claim_values(plain)
    if clause is None or not said:
        return Verification(verdict="NOT_IN_WRITING")
    have = doc_values(clause.text)
    if all(sv in have for sv in said):
        num = said[0]
        q = _clause_sentence(clause, lambda s: num in doc_values(s))
        return Verification(verdict="WRITTEN", clause_id=clause.id, clause_quote=q)
    units = {u for u, _ in said}
    if category in CONTRADICTABLE and any(u in units for u, _ in have):
        q = _clause_sentence(clause, lambda s: any(u in units for u, _ in doc_values(s)))
        return Verification(verdict="CONTRADICTED", clause_id=clause.id, clause_quote=q)
    return Verification(verdict="NOT_IN_WRITING")


def run_rules(transcript: str, clauses: list[Clause], lang_code: str) -> PipelineResult:
    lang = get_lang(lang_code)
    t0 = time.perf_counter()
    results = []
    for i, (sentence, cat) in enumerate(extract(transcript)):
        nums = [f"{v / 100_000:g} lakh" if u == "amount" else f"{v:g} {u}"
                for u, v in claim_values(_PRODUCT.sub(" ", sentence))]
        # same code-level grounding check as the Evon path (quote in transcript, clause quote, numbers)
        claim = ExtractedClaim(quote=sentence, claim_en="-", category=CATEGORY_OUT.get(cat, cat), numbers=nums)
        v = judge(sentence, cat, clauses)
        verdict, grounded, reason, clause = ground_check(claim, v, transcript, clauses)
        r = ClaimResult(idx=i, quote=sentence, claim_en="", category=claim.category, numbers=nums,
                        verdict=verdict, grounded=grounded, reason=reason,
                        explain_en=localtext.EXPLAIN["en"][verdict], explain_local=localtext.EXPLAIN[lang.code][verdict],
                        ask_agent=localtext.ASK[lang.code])
        if clause is not None and verdict != "NOT_IN_WRITING":
            r.clause_id, r.clause_quote, r.clause_page = clause.id, v.clause_quote, clause.page
        results.append(r)
    summary = localtext.fallback_summary(lang.code, [(r.verdict, r.category) for r in results])
    trace = {"engine": {"provider": "none", "label": LABEL, "quant": None, "model": None, "mode": "B"},
             "evon_model": None, "evon_calls": [], "pipeline_ms": int((time.perf_counter() - t0) * 1000),
             "claims": len(results)}
    return PipelineResult(claims=results, summary=summary, trace=trace)
