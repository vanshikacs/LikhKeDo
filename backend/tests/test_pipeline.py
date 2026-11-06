import asyncio
from pathlib import Path

import pytest

from app.evon import EvonClient, EvonJSONError
from app.ingest import parse_pdf
from app.pipeline import ground_check, numbers_in_clause, run_pipeline
from app.schemas import Extraction, ExtractedClaim, Verification

from .fake_evon import FakeOpenAI

ROOT = Path(__file__).resolve().parents[2]
CLAUSES = parse_pdf((ROOT / "demo/policy/bharosa_suraksha_plus_cis.pdf").read_bytes())
PITCH = (ROOT / "demo/pitches/hi_hinglish.txt").read_text(encoding="utf-8")
RETURNS = "Returns are not guaranteed. The illustrated rates of 4% and 8% p.a. are not upper or lower limits"


def claim(quote, en="x", numbers=()):
    return ExtractedClaim(quote=quote, claim_en=en, category="other", numbers=list(numbers))


# ---------- ground_check edge cases ----------

def test_written_grounded():
    c = claim("10 लाख का life cover", "Life cover of Rs 10 lakh", ["10 lakh"])
    v = Verification(verdict="WRITTEN", clause_id="p1-s6", clause_quote="Sum assured on death: Rs 10,00,000")
    assert ground_check(c, v, PITCH, CLAUSES)[:2] == ("WRITTEN", True)


def test_hallucinated_quote_downgraded():
    c = claim("आपको हर महीने बोनस मिलेगा")
    v = Verification(verdict="CONTRADICTED", clause_id="p2-s4", clause_quote="No bonus is declared")
    verdict, grounded, reason, _ = ground_check(c, v, PITCH, CLAUSES)
    assert (verdict, grounded) == ("NOT_IN_WRITING", False) and "transcript" in reason


def test_invented_clause_quote_downgraded():
    c = claim("returns guaranteed हैं, हर साल minimum 12 percent")
    v = Verification(verdict="CONTRADICTED", clause_id="p2-s2", clause_quote="Returns are guaranteed at 12% for life")
    verdict, grounded, reason, _ = ground_check(c, v, PITCH, CLAUSES)
    assert verdict == "NOT_IN_WRITING" and not grounded and "document" in reason


def test_wrong_clause_id_is_corrected():
    c = claim("returns guaranteed हैं, हर साल minimum 12 percent")
    v = Verification(verdict="CONTRADICTED", clause_id="p1-s1", clause_quote=RETURNS)
    verdict, grounded, _, clause = ground_check(c, v, PITCH, CLAUSES)
    assert (verdict, grounded, clause.id) == ("CONTRADICTED", True, "p2-s2")


def test_written_with_missing_number_downgraded():
    c = claim("सिर्फ़ 5 साल premium भरना है", "Premium for only 5 years", ["5 years"])
    v = Verification(verdict="WRITTEN", clause_id="p1-s5", clause_quote="Premium paying term: 10 years")
    verdict, grounded, reason, _ = ground_check(c, v, PITCH, CLAUSES)
    assert verdict == "NOT_IN_WRITING" and "5 years" in reason


def test_numbers_with_lakh_and_percent():
    assert numbers_in_clause(["10 lakh"], "Sum assured on death: Rs 10,00,000")[0]
    assert numbers_in_clause(["30 days"], "within 30 days from the date of receipt")[0]
    assert not numbers_in_clause(["12%"], "illustrated rates of 4% and 8% p.a.")[0]
    assert not numbers_in_clause(["बारह"], "12 percent")[0]


def test_none_verification_downgraded():
    c = claim("ये FD से तो पक्का better है")
    assert ground_check(c, None, PITCH, CLAUSES)[:2] == ("NOT_IN_WRITING", False)


# ---------- Evon JSON repair ----------

def test_json_repair_retry_succeeds():
    fake = FakeOpenAI({"claims": [{"quote": "q", "claim_en": "e", "category": "returns"}]}, lambda p: {},
                      bad_first={"extract"})
    out = asyncio.run(EvonClient(fake).chat_json([{"role": "system", "content": "You extract"}], False, 100, Extraction))
    assert out.claims[0].quote == "q" and len(fake.requests) == 2
    assert "not valid JSON" in fake.requests[1]["messages"][-1]["content"]
    assert fake.requests[0]["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}


def test_json_repair_gives_up():
    class Always:
        def __init__(self):
            self.n = 0
            from types import SimpleNamespace
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        async def create(self, **kw):
            from .fake_evon import _resp
            self.n += 1
            return _resp("not json at all")

    a = Always()
    with pytest.raises(EvonJSONError):
        asyncio.run(EvonClient(a).chat_json([{"role": "system", "content": "x"}], False, 100, Extraction))
    assert a.n == 2


# ---------- full pipeline on the demo pitch ----------

EXTRACT = {"claims": [
    {"quote": "returns guaranteed हैं, हर साल minimum 12 percent", "claim_en": "Returns are guaranteed at a minimum of 12% a year", "category": "returns", "numbers": ["12%"]},
    {"quote": "सिर्फ़ 5 साल premium भरना है", "claim_en": "Premium has to be paid for only 5 years", "category": "premium_term", "numbers": ["5 years"]},
    {"quote": "10 लाख का life cover", "claim_en": "Life cover of Rs 10 lakh", "category": "cover", "numbers": ["10 lakh"]},
    {"quote": "कभी भी loan ले सकते हैं, वो भी 0 percent interest पर", "claim_en": "A loan can be taken any time at 0% interest", "category": "liquidity", "numbers": ["0%"]},
    {"quote": "ये FD से तो पक्का better है", "claim_en": "The plan is better than a fixed deposit", "category": "returns", "numbers": []},
    {"quote": "30 दिन के अंदर पसंद नहीं आई तो आप return कर सकते हैं", "claim_en": "The policy can be returned within 30 days", "category": "other", "numbers": ["30 days"]},
]}


def verify(promise: str) -> dict:
    base = {"explain_en": "e", "explain_local": "दस्तावेज़ में लिखा है", "ask_agent": "क्या आप यह लिखित में देंगे?"}
    if "guaranteed" in promise:
        return {**base, "verdict": "CONTRADICTED", "clause_id": "p2-s2", "clause_quote": "Returns are not guaranteed."}
    if "5 years" in promise:
        return {**base, "verdict": "CONTRADICTED", "clause_id": "p1-s5", "clause_quote": "Premium paying term: 10 years."}
    if "10 lakh" in promise:
        return {**base, "verdict": "WRITTEN", "clause_id": "p1-s6", "clause_quote": "Sum assured on death: Rs 10,00,000 (Rupees ten lakh)."}
    if "30 days" in promise:
        # English-only explain_local: must be fixed by the script check
        return {**base, "explain_local": "It is written.", "verdict": "WRITTEN", "clause_id": "p3-s3",
                "clause_quote": "you may return the policy within 30 days from the date of receipt"}
    return {**base, "verdict": "NOT_IN_WRITING", "clause_id": None, "clause_quote": None}


def test_pipeline_end_to_end_with_fake_evon():
    fake = FakeOpenAI(EXTRACT, verify, bad_first={"verify"})
    events = []
    res = asyncio.run(run_pipeline(PITCH, CLAUSES, "hi", EvonClient(fake), events.append))
    verdicts = [r.verdict for r in res.claims]
    assert verdicts == ["CONTRADICTED", "CONTRADICTED", "WRITTEN", "NOT_IN_WRITING", "NOT_IN_WRITING", "WRITTEN"]
    assert all(r.grounded for r in res.claims)
    assert res.claims[5].explain_local == "कृपया लिखित में माँगिए"   # localized after script check
    assert res.claims[0].clause_page == 2
    assert events[0] == {"stage": "extracting"} and {"stage": "checking", "i": 6, "n": 6} in events
    assert "<pauses>" in res.summary
    verify_reqs = [r for r in fake.requests if r["messages"][0]["content"].startswith("You compare")]
    assert all(r["extra_body"]["chat_template_kwargs"]["enable_thinking"] for r in verify_reqs)
    assert all(r["max_tokens"] == 4096 and r["temperature"] == 0.6 and r["top_p"] == 0.95 for r in verify_reqs)
    assert "Hindi using Devanagari script" in verify_reqs[0]["messages"][0]["content"]
