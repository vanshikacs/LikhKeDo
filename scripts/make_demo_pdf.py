"""Generate the fictional Customer Information Sheet used by the demo.

Everything here is fictional: "Bharosa Life Insurance Ltd (FICTIONAL)" does not exist.
Output: demo/policy/bharosa_suraksha_plus_cis.pdf (4 pages, diagonal watermark on every page).

Usage: backend/.venv/Scripts/python scripts/make_demo_pdf.py   (needs: pip install -r scripts/requirements.txt)
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path(__file__).resolve().parents[1] / "demo" / "policy" / "bharosa_suraksha_plus_cis.pdf"
WATERMARK = "SAMPLE - FICTIONAL - FOR DEMO ONLY"

ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=16, spaceAfter=4)
SUB = ParagraphStyle("sub", parent=ss["Normal"], fontSize=9, alignment=1, textColor=colors.grey)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
P = ParagraphStyle("p", parent=ss["Normal"], fontSize=10, leading=14, spaceAfter=6)


def watermark(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 34)
    canvas.setFillColor(colors.Color(0.85, 0.85, 0.85))
    canvas.translate(A4[0] / 2, A4[1] / 2)
    canvas.rotate(45)
    canvas.drawCentredString(0, 0, WATERMARK)
    canvas.restoreState()
    canvas.setFont("Helvetica", 8)
    canvas.drawString(20 * mm, 10 * mm, "Bharosa Life Insurance Ltd (FICTIONAL) - Customer Information Sheet - "
                                         f"Page {doc.page} of 4")


def table(rows, widths):
    t = Table(rows, colWidths=widths)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.92, 0.92, 0.92)),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    return t


def c(n: int, text: str) -> Paragraph:
    return Paragraph(f"{n}. {text}", P)


def build() -> None:
    story = [
        Paragraph("Customer Information Sheet", H1),
        Paragraph("Bharosa Life Insurance Ltd (FICTIONAL) - Suraksha Plus Guaranteed Wealth Plan", SUB),
        Spacer(1, 6),
        Paragraph("Part A - About the policy", H2),
        c(1, "Name of insurer: Bharosa Life Insurance Ltd (FICTIONAL). This document is a sample created for a "
             "software demonstration and does not describe any real insurance product."),
        c(2, "Name of product: Suraksha Plus Guaranteed Wealth Plan. Type of product: a non-linked, "
             "non-participating individual savings life insurance plan."),
        c(3, "Policy term: 15 years from the date of commencement of the policy."),
        c(4, "Premium paying term: 10 years. Premiums are payable every year for the full premium paying term of "
             "10 years."),
        c(5, "Sum assured on death: Rs 10,00,000 (Rupees ten lakh). This amount is payable to the nominee if the "
             "life assured dies during the policy term while the policy is in force."),
        c(6, "Annualised premium: Rs 1,00,000 per year for the illustrated case of a 40-year-old life assured."),
        PageBreak(),
        Paragraph("Part B - Benefits and returns", H2),
        c(7, "Maturity benefit: on survival to the end of the policy term, the fund value built up from premiums "
             "is paid as a lump sum."),
        c(8, "Returns are not guaranteed. The illustrated rates of 4% and 8% p.a. are not upper or lower limits of "
             "what you might get back, as the value of your policy depends on a number of factors including "
             "future investment performance."),
        c(9, "Benefit illustration for an annualised premium of Rs 1,00,000:"),
        table([["Assumed rate", "Maturity value after 15 years (Rs)"],
               ["4% p.a.", "12,40,000"],
               ["8% p.a.", "16,85,000"]], [60 * mm, 90 * mm]),
        Spacer(1, 8),
        c(10, "Bonus: this is a non-participating plan. No bonus is declared or payable under this policy."),
        PageBreak(),
        Paragraph("Part C - Lock-in, surrender and free look", H2),
        c(11, "Lock-in period: 5 years. No surrender or partial withdrawal is allowed during the first 5 policy "
              "years."),
        c(12, "Surrender charges: surrender charges apply when the policy is surrendered after the lock-in period, "
              "as shown below."),
        table([["Policy year of surrender", "Surrender charge (% of fund value)"],
               ["6", "6%"], ["7", "5%"], ["8", "4%"], ["9", "3%"], ["10 and later", "Nil"]],
              [60 * mm, 90 * mm]),
        Spacer(1, 8),
        c(13, "Free-look period: you may return the policy within 30 days from the date of receipt of the policy "
              "document if you disagree with any of its terms. The premium is refunded after deducting stamp duty "
              "and the cost of cover for the period."),
        c(14, "Tax benefits: tax benefits, if any, are as per prevailing tax laws, subject to change. Please "
              "consult your tax adviser."),
        PageBreak(),
        Paragraph("Part D - Charges, exclusions and grievances", H2),
        c(15, "Charges deducted from the fund:"),
        table([["Charge", "Amount"],
               ["Premium allocation charge", "5% of premium in years 1 to 3"],
               ["Policy administration charge", "Rs 600 per year"],
               ["Mortality charge", "As per the age of the life assured, deducted monthly"],
               ["Fund management charge", "1.35% p.a. of fund value"]], [70 * mm, 90 * mm]),
        Spacer(1, 8),
        c(16, "Exclusions: suicide within 12 months of the date of commencement of the policy. In this case 80% "
              "of the premiums paid are refunded to the nominee."),
        c(17, "Grievances: write to the Grievance Officer, Bharosa Life Insurance Ltd (FICTIONAL), at "
              "grievance@bharosalife.example. This sample document lists no real address or phone number."),
        c(18, "This Customer Information Sheet is a summary. In case of any conflict, the policy contract "
              "prevails."),
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title="Suraksha Plus CIS (FICTIONAL)", author="LikhKeDo demo")
    doc.build(story, onFirstPage=watermark, onLaterPages=watermark)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    build()
