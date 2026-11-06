from pathlib import Path

import pytest

from app.ingest import ClauseIndex, IngestError, full_text, normalise, parse_pdf

DEMO_PDF = Path(__file__).resolve().parents[2] / "demo" / "policy" / "bharosa_suraksha_plus_cis.pdf"


@pytest.fixture(scope="module")
def clauses():
    return parse_pdf(DEMO_PDF.read_bytes())


def test_normalise():
    assert normalise("Returns  १२% GUARANTEED") == "returns 12 percent guaranteed"
    assert normalise("௧௦ pratishat") == "10 percent"
    assert normalise("Rs 10,00,000") == "rs 1000000"
    assert normalise("12 per cent") == "12 percent"


def test_watermark_and_footer_removed(clauses):
    text = " ".join(c.text for c in clauses)
    assert "SAMPLE - FICTIONAL" not in text
    assert "Page 2 of 4" not in text


def test_clause_ids_and_pages(clauses):
    assert all(c.id == f"p{c.page}-s{c.id.split('-s')[1]}" for c in clauses)
    assert {c.page for c in clauses} == {1, 2, 3, 4}


def test_returns_query_finds_not_guaranteed(clauses):
    top = ClauseIndex(clauses).search("returns guaranteed 12 percent", k=3)
    assert any("Returns are not guaranteed" in c.text for c in top)


def test_premium_paying_term_first(clauses):
    top = ClauseIndex(clauses).search("premium paying term", k=5)
    assert top[0].text.startswith("4. Premium paying term: 10 years")


def test_full_text_respects_limit(clauses):
    assert len(full_text(clauses, max_chars=500)) <= 500
    assert "[p1-s" in full_text(clauses)


def test_rejects_pdf_without_text():
    canvas = pytest.importorskip("reportlab.pdfgen.canvas")
    import io

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.showPage()
    c.save()
    with pytest.raises(IngestError, match="no extractable text"):
        parse_pdf(buf.getvalue())


def test_rejects_garbage():
    with pytest.raises(IngestError):
        parse_pdf(b"not a pdf")
