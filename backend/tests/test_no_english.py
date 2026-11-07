"""No English sentences in hi/mr/ta user-facing text produced without the model (slip, fallbacks, speak text)."""
import re

import pytest

from app import localtext
from app.report import render_slip
from app.routes.cases import ANNOUNCE, _speak_text

# Product names and loan words that may stay in Latin script inside Indic text.
ALLOW = ["Suraksha Plus Guaranteed Wealth Plan", "Bharosa Life", "LikhKeDo", "free look", "free-look", "lock-in",
         "premium", "loan", "FD", "ULIP", "PDF", "CIS", "Chrome", "Edge", "Safari", "GPU", "Evon"]
RUN = re.compile(r"[A-Za-z][A-Za-z'’]*(?:[\s,.-]+[A-Za-z][A-Za-z'’]*){2,}")


def english_runs(text: str) -> list[str]:
    text = re.sub(r"<style.*?</style>|<[^>]+>|&[a-z]+;", " ", text, flags=re.S)
    for a in sorted(ALLOW, key=len, reverse=True):
        text = re.sub(re.escape(a), " ", text, flags=re.I)
    return RUN.findall(text)


def report(lang: str) -> dict:
    claims = [{"id": f"c{i}", "quote": "हर साल 12 percent", "claim_en": "Returns are guaranteed at 12% a year",
               "category": "returns", "numbers": ["12%"], "verdict": v, "clause_id": "p2-s2" if v != "NOT_IN_WRITING" else None,
               "clause_quote": "रिटर्न बाज़ार से जुड़े हैं" if v != "NOT_IN_WRITING" else None, "clause_page": 2,
               "explain_en": "The document says returns are not guaranteed.", "explain_local": "", "ask_agent": "",
               "grounded": True, "reason": None}
              for i, v in enumerate(["CONTRADICTED", "NOT_IN_WRITING", "WRITTEN"])]
    return {"id": "x", "lang": lang, "product_label": "Suraksha Plus Guaranteed Wealth Plan", "claims": claims,
            "summary": "s"}


def test_checker_catches_english():
    assert english_runs("यह plan is not guaranteed at all")
    assert not english_runs("इसमें returns guaranteed हैं, premium भरना है")


@pytest.mark.parametrize("lang", ["hi", "mr", "ta"])
def test_fixed_text_has_no_english(lang):
    rep = report(lang)
    texts = [render_slip(rep), ANNOUNCE[lang], localtext.DISCLAIMER[lang], localtext.ASK[lang],
             localtext.NO_PROMISES[lang], *localtext.EXPLAIN[lang].values(), *localtext.CATEGORY[lang].values(),
             localtext.fallback_summary(lang, [("CONTRADICTED", "returns"), ("NOT_IN_WRITING", "liquidity")]),
             localtext.fallback_summary(lang, [("WRITTEN", "cover")]),
             *(_speak_text(rep, c["id"]) for c in rep["claims"])]
    for t in texts:
        assert not english_runs(t), (lang, english_runs(t), t[:120])


@pytest.mark.parametrize("lang", ["hi", "mr", "ta"])
def test_speak_text_never_uses_explain_en(lang):
    rep = report(lang)
    for c in rep["claims"]:
        assert "document says" not in _speak_text(rep, c["id"])
