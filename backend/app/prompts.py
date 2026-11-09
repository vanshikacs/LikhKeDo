"""All Evon prompts in one place. Every prompt that produces user-facing text names language AND script."""
from __future__ import annotations

import json

from .langs import Lang

EXTRACT_SYSTEM = """You extract promises a salesperson made about a financial product.
Return ONLY JSON matching this schema, with no other text:
{"claims":[{"quote":"<words copied exactly from the transcript>","claim_en":"<one plain English sentence>","category":"<category>","numbers":["<number with unit, digits>"]}]}
Rules:
- 'quote' must be copied exactly from the transcript (same script, same words). Never translate or fix it.
- 'claim_en' is one plain English sentence stating the promise.
- Categories: returns, guarantee, lock_in, premium_term, policy_term, charges, liquidity, tax, cover, other.
- Extract numbers as stated, written with digits and their unit (e.g. "12%", "5 years", "10 lakh", "0%"). Spoken number words become digits (बारह -> 12).
- One claim per promise. Ignore greetings, small talk and sales pressure that promises nothing.
- Maximum 12 claims. If there are no promises, return {"claims":[]}."""

EXTRACT_FEWSHOT = [
    {"role": "user", "content": "TRANSCRIPT (hi-IN, code-mixed):\nनमस्ते जी। इस plan में returns guaranteed हैं, हर साल 10 percent पक्का मिलेगा। चाय लेंगे?"},
    {"role": "assistant", "content": json.dumps({"claims": [
        {"quote": "इस plan में returns guaranteed हैं, हर साल 10 percent पक्का मिलेगा",
         "claim_en": "The plan guarantees returns of 10% every year.", "category": "returns",
         "numbers": ["10%"]}]}, ensure_ascii=False)},
    {"role": "user", "content": "TRANSCRIPT (hi-IN, code-mixed):\nSir premium sirf 7 saal bharna hai, policy term 20 saal ka hai."},
    {"role": "assistant", "content": json.dumps({"claims": [
        {"quote": "premium sirf 7 saal bharna hai", "claim_en": "Premium has to be paid for only 7 years.",
         "category": "premium_term", "numbers": ["7 years"]},
        {"quote": "policy term 20 saal ka hai", "claim_en": "The policy term is 20 years.",
         "category": "policy_term", "numbers": ["20 years"]}]}, ensure_ascii=False)},
]

DECIDE_RULES = """How to decide (check in this order):
1. The promise says returns/bonus/amount are guaranteed, fixed or assured, and the document says they are not guaranteed or depend on performance: CONTRADICTED.
2. Same topic, different number (example: promise "premium for only 7 years", document "Premium paying term: 20 years"): CONTRADICTED. Quote the clause that states the document's number.
3. WRITTEN only when the document states the same fact with the same number.
4. Opinions, comparisons with other products, or things the document never mentions (example: "better than gold", "the best plan in the market"): NOT_IN_WRITING. Do not stretch an unrelated clause to contradict them.
"""

VERIFY_SYSTEM = """You compare one spoken promise with the official policy document.
Decide:
- WRITTEN: the document clearly states the same thing.
- CONTRADICTED: the document clearly states something incompatible.
- NOT_IN_WRITING: the document does not address it.
""" + DECIDE_RULES + """'clause_quote' must be copied exactly from one provided clause (a sentence or phrase, not the whole document) and 'clause_id' must be that clause's id. For NOT_IN_WRITING use null for both.
If unsure, choose NOT_IN_WRITING.
Write 'explain_en' as one short English sentence.
Write 'explain_local' and 'ask_agent' in {lang_name} using {script_name} script, short and simple, for an older reader. English product words (premium, lock-in, FD) may stay as they are.
'ask_agent' is one polite question the buyer can ask the seller, asking for it in writing.
Never accuse the seller; say what the document says.
Return ONLY JSON:
{{"verdict":"WRITTEN|CONTRADICTED|NOT_IN_WRITING","clause_id":"<id or null>","clause_quote":"<exact words or null>","explain_en":"...","explain_local":"...","ask_agent":"..."}}"""

VERIFY_BATCH_SYSTEM = """You compare several spoken promises with the official policy document, one by one.
For EACH promise decide:
- WRITTEN: the document clearly states the same thing.
- CONTRADICTED: the document clearly states something incompatible.
- NOT_IN_WRITING: the document does not address it.
""" + DECIDE_RULES + """'clause_quote' must be copied exactly from one clause of the document (a sentence or phrase, not the whole document) and 'clause_id' must be that clause's id in square brackets. For NOT_IN_WRITING use null for both.
If unsure, choose NOT_IN_WRITING.
'explain_en': one short English sentence.
'explain_local' and 'ask_agent': in {lang_name} using {script_name} script, short and simple, for an older reader. English product words (premium, lock-in, FD) may stay as they are.
'ask_agent' is one polite question the buyer can ask the seller, asking for it in writing.
Never accuse the seller; say what the document says.
Do not think out loud. Return ONLY one JSON object, one result per promise id:
{{"results":[{{"id":0,"verdict":"WRITTEN|CONTRADICTED|NOT_IN_WRITING","clause_id":"<id or null>","clause_quote":"<exact words or null>","explain_en":"...","explain_local":"...","ask_agent":"..."}}]}}"""

SUMMARY_SYSTEM = """You speak to an older family member, in {lang_name} using {script_name} script, after checking a sales pitch against the policy document.
Say how many promises are different in the document or missing from it, name the most important one by its topic, and advise asking for it in writing before signing.
2 to 4 short sentences. Put the tag <pauses> between sentences. You may start with <slow>.
No markdown, lists, labels or emojis. Do not repeat these instructions or the input lines. English only for product words (premium, lock-in, FD, policy).
Never say the seller lied. Return ONLY JSON: {{"text":"..."}}"""

LOCALIZE_SYSTEM = """Rewrite the given text in {lang_name} using ONLY {script_name} script (English product words like premium or FD may stay).
Keep the meaning. Short and simple, for an older reader. Return ONLY JSON: {{"text":"..."}}"""


def extract_messages(transcript: str, lang: Lang) -> list[dict]:
    return [{"role": "system", "content": EXTRACT_SYSTEM}, *EXTRACT_FEWSHOT,
            {"role": "user", "content": f"TRANSCRIPT ({lang.prisma.split(',')[0]}, code-mixed):\n{transcript}"}]


def verify_messages(claim_quote: str, claim_en: str, numbers: list[str], cis_text: str,
                    top_clauses: list, lang: Lang) -> list[dict]:
    clauses = "\n".join(f"[{c.id}] (page {c.page}) {c.text}" for c in top_clauses)
    user = (f"PROMISE (spoken): {claim_quote}\nPROMISE (English): {claim_en}\n"
            f"NUMBERS: {', '.join(numbers) or 'none'}\n\n"
            f"MOST RELEVANT CLAUSES:\n{clauses}\n\nFULL DOCUMENT:\n{cis_text}")
    return [{"role": "system", "content": VERIFY_SYSTEM.format(lang_name=lang.name, script_name=lang.script)},
            {"role": "user", "content": user}]


def verify_batch_messages(claims: list, cis_text: str, lang: Lang) -> list[dict]:
    promises = "\n".join(f"[{i}] spoken: {c.quote} | English: {c.claim_en} | numbers: {', '.join(c.numbers) or 'none'}"
                         for i, c in enumerate(claims))
    user = f"PROMISES:\n{promises}\n\nDOCUMENT:\n{cis_text}"
    return [{"role": "system", "content": VERIFY_BATCH_SYSTEM.format(lang_name=lang.name, script_name=lang.script)},
            {"role": "user", "content": user}]


def summary_messages(claims: list[dict], lang: Lang) -> list[dict]:
    """claims: [{verdict, category}]. Topics are given already in the buyer's language (no English claim text)."""
    from .localtext import CATEGORY
    cats = CATEGORY[lang.code]
    rows = []
    for verdict, label in (("CONTRADICTED", "Different in the document"), ("NOT_IN_WRITING", "Not in the document"),
                           ("WRITTEN", "Written in the document")):
        topics = [cats.get(c["category"], cats["other"]) for c in claims if c["verdict"] == verdict]
        rows.append(f"{label}: {len(topics)}" + (" - " + "; ".join(topics) if topics else ""))
    user = f"Promises checked: {len(claims)}\n" + "\n".join(rows)
    return [{"role": "system", "content": SUMMARY_SYSTEM.format(lang_name=lang.name, script_name=lang.script)},
            {"role": "user", "content": user}]


def localize_messages(text: str, lang: Lang) -> list[dict]:
    return [{"role": "system", "content": LOCALIZE_SYSTEM.format(lang_name=lang.name, script_name=lang.script)},
            {"role": "user", "content": text}]
