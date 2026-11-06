"""Supported buyer languages: Prisma hints, Timbre language, and the script Evon must write in."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Lang:
    code: str           # our short code
    name: str           # language name for prompts
    script: str         # script name for prompts
    prisma: str         # Prisma language_code (buyer language + English)
    tts: str            # Timbre "language"
    ranges: tuple[tuple[int, int], ...]  # Unicode ranges of the script


LANGS: dict[str, Lang] = {
    "hi": Lang("hi", "Hindi", "Devanagari", "hi-IN,en-IN", "hi-IN", ((0x0900, 0x097F),)),
    "mr": Lang("mr", "Marathi", "Devanagari", "mr-IN,en-IN", "mr-IN", ((0x0900, 0x097F),)),
    "ta": Lang("ta", "Tamil", "Tamil", "ta-IN,en-IN", "ta-IN", ((0x0B80, 0x0BFF),)),
    "en": Lang("en", "English", "Latin", "en-IN", "en-IN", ((0x0041, 0x007A),)),
}


def get_lang(code: str) -> Lang:
    try:
        return LANGS[code]
    except KeyError:
        raise ValueError(f"unsupported language '{code}'; use one of {', '.join(LANGS)}") from None


def script_ratio(text: str, lang: Lang) -> float:
    """Share of letters in `text` that belong to the language's script (ignores digits, spaces, punctuation)."""
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    inside = sum(1 for ch in letters if any(lo <= ord(ch) <= hi for lo, hi in lang.ranges))
    return inside / len(letters)
