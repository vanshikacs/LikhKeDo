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

VERIFY_SYSTEM = """You compare one spoken promise with the official policy document.
Decide:
- WRITTEN: the document clearly states the same thing.
- CONTRADICTED: the document clearly states something incompatible.
- NOT_IN_WRITING: the document does not address it.
'clause_quote' must be copied exactly from one provided clause (a sentence or phrase, not the whole document) and 'clause_id' must be that clause's id. For NOT_IN_WRITING use null for both.
If unsure, choose NOT_IN_WRITING.
Write 'explain_en' as one short English sentence.
Write 'explain_local' and 'ask_agent' in {lang_name} using {script_name} script, short and simple, for an older reader. English product words (premium, lock-in, FD) may stay as they are.
'ask_agent' is one polite question the buyer can ask the seller, asking for it in writing.
Never accuse the seller; say what the document says.
Return ONLY JSON:
{{"verdict":"WRITTEN|CONTRADICTED|NOT_IN_WRITING","clause_id":"<id or null>","clause_quote":"<exact words or null>","explain_en":"...","explain_local":"...","ask_agent":"..."}}"""

SUMMARY_SYSTEM = """Write a short spoken summary for text-to-speech in {lang_name} using {script_name} script.
2 to 4 short sentences: how many promises are not on paper, the most important one (by its topic), and advise to ask for it in writing.
You get each promise's verdict and topic category (returns, premium_term, lock_in, liquidity, cover, tax, ...); describe topics in {lang_name}.
Insert the tag <pauses> between sentences. Optionally start with <slow>.
No markdown, no emojis, no lists, no English except product terms (premium, lock-in, FD, policy).
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


def summary_messages(claims: list[dict], lang: Lang) -> list[dict]:
    lines = [f"- {c['verdict']}: {c['category']}" for c in claims]
    return [{"role": "system", "content": SUMMARY_SYSTEM.format(lang_name=lang.name, script_name=lang.script)},
            {"role": "user", "content": "Verdicts:\n" + "\n".join(lines)}]


def localize_messages(text: str, lang: Lang) -> list[dict]:
    return [{"role": "system", "content": LOCALIZE_SYSTEM.format(lang_name=lang.name, script_name=lang.script)},
            {"role": "user", "content": text}]
