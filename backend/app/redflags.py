"""Live red-flag phrases spotted in streamed captions. Rules only; no model involved."""
from __future__ import annotations

import re

# Prisma codemix often writes small numbers as words ("पाँच साल", "बारह percent").
_NUMWORDS = ("ek|do|teen|char|chaar|paanch|panch|chhe|saat|aath|nau|das|barah|baarah|pandrah|bees|"
             "एक|दो|तीन|चार|पाँच|पांच|छह|छः|सात|आठ|नौ|दस|बारह|पंद्रह|बीस|"
             "पाच|सहा|आठ|दहा|बारा|पंधरा|"
             "ஒன்று|இரண்டு|மூன்று|நான்கு|ஐந்து|ஆறு|ஏழு|எட்டு|பத்து")
_N = rf"(?:\d+|{_NUMWORDS})"

# label -> pattern (Latin, Devanagari and Tamil spellings as Prisma codemix may produce them)
RULES: dict[str, re.Pattern] = {
    "guaranteed": re.compile(r"guarante+d?|गारंटी(?:ड)?|गॅरंटी|கேரண்டி|உத்தரவாத", re.I),
    "pakka": re.compile(r"\bpakk[aei]\b|पक्का|पक्की|पक्के|நிச்சயம்|கண்டிப்பா", re.I),
    "FD jaisa": re.compile(r"\bf\.?\s?d\.?\s*(?:jaisa|jaise|jaisi|जैसा|जैसे|जैसी|सारखा|सारखं|மாதிரி)|"
                           r"एफडी\s*(?:जैसा|जैसे|जैसी)", re.I),
    "no lock-in": re.compile(r"no\s+lock[\s-]?in|lock[\s-]?in\s*(?:nahi|nahin|नहीं|नाही|இல்லை)|"
                             r"लॉक[\s-]?इन\s*नहीं", re.I),
    "tax free": re.compile(r"tax[\s-]?free|टैक्स\s*फ्री|टॅक्स\s*फ्री|வரி\s*இல்லை", re.I),
    "double": re.compile(r"\bdouble\b|डबल|दोगुना|दुगना|இரட்டிப்பு", re.I),
    "sirf N saal": re.compile(rf"(?:sirf|only|सिर्फ़?|सिर्फ|फक्त|மட்டும்)\s*\S{{0,6}}\s*{_N}\s*(?:saal|years?|साल|वर्ष|वर्षं|वर्षे)|"
                              rf"{_N}\s*(?:வருஷம்|வருடம்)\s*மட்டும்", re.I),
    "risk nahi": re.compile(r"(?:no|koi)\s+risk|risk\s*(?:nahi|nahin|नहीं|नाही|இல்லை)|रिस्क\s*नहीं", re.I),
}


def find_redflags(text: str) -> list[str]:
    """Return the labels of all rules that match, in a stable order."""
    return [label for label, pat in RULES.items() if pat.search(text)]
