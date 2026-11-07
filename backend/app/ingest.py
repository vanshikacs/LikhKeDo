"""PDF -> clauses, normalisation and BM25 retrieval."""
from __future__ import annotations

import io
import re
from collections import Counter
from dataclasses import dataclass

import pdfplumber
from rank_bm25 import BM25Okapi


class IngestError(ValueError):
    """The PDF cannot be used (no extractable text, unreadable file). `code` is localized in the frontend."""

    def __init__(self, message: str, code: str = "PDF_UNREADABLE"):
        super().__init__(message)
        self.code = code


@dataclass
class Clause:
    id: str
    page: int
    section: str
    text: str


# ---------- normalisation ----------

_DIGITS = {}
for base in (0x0966, 0x0BE6, 0x09E6, 0x0A66, 0x0AE6, 0x0C66, 0x0CE6, 0x0D66):  # Devanagari, Tamil, ...
    for i in range(10):
        _DIGITS[base + i] = str(i)
_DIGIT_TABLE = str.maketrans({chr(k): v for k, v in _DIGITS.items()})
_PERCENT = re.compile(r"\s*%|\bper\s*cent\b|\bpercent\b|\bpratishat\b|प्रतिशत|परसेंट|पर्सेंट|சதவீதம்", re.I)
_SPACES = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Lowercase, ASCII digits, 'percent' for every spelling of %, single spaces."""
    t = text.translate(_DIGIT_TABLE).lower()
    t = re.sub(r"(?<=\d),(?=\d)", "", t)          # 10,00,000 -> 1000000
    t = _PERCENT.sub(" percent", t)
    return _SPACES.sub(" ", t).strip()


_TOKEN = re.compile(r"[\w]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(normalise(text))


# ---------- PDF parsing ----------

_NUMBERED = re.compile(r"^\s*(\d{1,3})[.)]\s+\S")
_HEADING = re.compile(r"^\s*(?i:part|section|schedule|annexure)\b.*$|^[A-Z][A-Z0-9 ,&/()-]{3,60}$")
# sentence end = . ! ? । followed by a capital/Indic letter (so "p.a. are" and "Rs. 10" don't split)
_SENTENCE = re.compile(r"(?<=[.!?।])\s+(?=[A-Zऀ-෿\"(])")


def _page_lines(page) -> list[str]:
    def keep(obj):
        if obj.get("object_type") != "char":
            return True
        m = obj.get("matrix")
        return not m or (abs(m[1]) < 1e-3 and abs(m[2]) < 1e-3)  # drop rotated text (watermarks)

    text = page.filter(keep).extract_text() or ""
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _is_heading(line: str) -> bool:
    return bool(_HEADING.match(line)) and not _NUMBERED.match(line) and len(line) < 80


def _split_long(text: str, max_sentences: int = 3) -> list[str]:
    sents = [s for s in _SENTENCE.split(text) if s.strip()]
    if len(sents) <= max_sentences:
        return [text]
    return [" ".join(sents[i:i + max_sentences]) for i in range(0, len(sents), max_sentences)]


def parse_pdf(data: bytes) -> list[Clause]:
    try:
        pdf = pdfplumber.open(io.BytesIO(data))
    except Exception as e:  # pdfminer raises many types
        raise IngestError(f"Could not read the PDF: {e.__class__.__name__}") from e
    with pdf:
        pages = [_page_lines(p) for p in pdf.pages]

    if sum(len(" ".join(p)) for p in pages) < 40:
        raise IngestError("This PDF has no extractable text (scanned images are not supported; we do not do OCR).",
                          "PDF_NO_TEXT")

    # drop running headers/footers: lines (digits masked) present on at least half the pages
    if len(pages) >= 2:
        mask = lambda s: re.sub(r"\d+", "#", s)  # noqa: E731
        counts = Counter(m for p in pages for m in {mask(l) for l in p})
        repeated = {m for m, n in counts.items() if n >= max(2, len(pages) / 2)}
        pages = [[l for l in p if mask(l) not in repeated] for p in pages]

    clauses: list[Clause] = []
    section = ""
    for pno, lines in enumerate(pages, start=1):
        blocks: list[tuple[str, str]] = []  # (section, text)
        cur: list[str] = []

        def flush():
            if cur:
                blocks.append((section, " ".join(cur)))
                cur.clear()

        for line in lines:
            if _is_heading(line):
                flush()
                section = line
            elif _NUMBERED.match(line):
                flush()
                cur.append(line)
            else:
                cur.append(line)
        flush()

        n = 0
        for sec, text in blocks:
            text = _SPACES.sub(" ", text).strip()
            if len(text) < 3:
                continue
            for part in _split_long(text):
                n += 1
                clauses.append(Clause(id=f"p{pno}-s{n}", page=pno, section=sec, text=part))
    if not clauses:
        raise IngestError("No clauses found in the PDF.", "PDF_NO_CLAUSES")
    return clauses


# ---------- retrieval ----------

class ClauseIndex:
    def __init__(self, clauses: list[Clause]):
        self.clauses = clauses
        self._bm25 = BM25Okapi([tokenize(c.text) or ["_"] for c in clauses])

    def search(self, query: str, k: int = 5) -> list[Clause]:
        q = tokenize(query)
        if not q:
            return self.clauses[:k]
        scores = self._bm25.get_scores(q)
        order = sorted(range(len(self.clauses)), key=lambda i: scores[i], reverse=True)
        return [self.clauses[i] for i in order[:k]]

    def get(self, clause_id: str) -> Clause | None:
        return next((c for c in self.clauses if c.id == clause_id), None)


def full_text(clauses: list[Clause], max_chars: int = 12000) -> str:
    out, size = [], 0
    for c in clauses:
        line = f"[{c.id}] (page {c.page}) {c.text}"
        if size + len(line) + 1 > max_chars:
            break
        out.append(line)
        size += len(line) + 1
    return "\n".join(out)
