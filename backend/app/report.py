"""Report JSON (shared by live cases and seeded demo cases) and the printable Likh Ke Do slip."""
from __future__ import annotations

import html
from datetime import datetime, timezone

from sqlmodel import select

from . import db
from .gnani import PRISMA_MODEL
from .localtext import DISCLAIMER as DISCLAIMERS

DISCLAIMER = DISCLAIMERS["en"]


def build_report(case_id: str) -> dict | None:
    with db.session() as s:
        case = s.get(db.Case, case_id)
        if case is None:
            return None
        claims = list(s.exec(select(db.Claim).where(db.Claim.case_id == case_id).order_by(db.Claim.idx)))
        segs = list(s.exec(select(db.Segment).where(db.Segment.case_id == case_id).order_by(db.Segment.idx)))
        calls = list(s.exec(select(db.ApiCall).where(db.ApiCall.case_id == case_id).order_by(db.ApiCall.id)))
        n_clauses = len(list(s.exec(select(db.ClauseRow.pk).where(db.ClauseRow.case_id == case_id))))
    counts = {v: sum(1 for c in claims if c.verdict == v) for v in ("WRITTEN", "CONTRADICTED", "NOT_IN_WRITING")}
    # Prisma per call: real request ids, mode, detected language, latency; cached results have no new call.
    seg_lang = {x.prisma_request_id: x.detected_lang for x in segs if x.prisma_request_id}
    stream_lang = next((x.detected_lang for x in segs if x.source == "stream" and x.detected_lang), None)
    prisma, seen = [], set()
    for a in calls:
        if a.service.startswith("prisma"):
            mode = "stream" if a.service == "prisma-stream" else "rest"
            seen.add(a.request_id)
            prisma.append({"request_id": a.request_id, "mode": mode, "status": a.status, "error_code": a.error_code,
                           "latency_ms": a.latency_ms, "cached": False,
                           "lang": stream_lang if mode == "stream" else seg_lang.get(a.request_id)})
    for x in segs:
        if x.prisma_request_id and x.prisma_request_id not in seen:
            seen.add(x.prisma_request_id)
            prisma.append({"request_id": x.prisma_request_id, "mode": x.source, "status": None, "error_code": None,
                           "latency_ms": None, "cached": True, "lang": x.detected_lang})
    trace = case.trace or {}
    return {
        "id": case.id,
        "lang": case.lang,
        "mode": case.mode,
        "status": case.status,
        "error": case.error,
        "product_label": case.product_label,
        "created_at": case.created_at.isoformat(),
        "expires_at": case.expires_at.isoformat(),
        "summary": case.summary,
        "engine": trace.get("engine"),
        "counts": counts,
        "clauses": n_clauses,
        "transcript": [{"idx": x.idx, "text": x.text, "source": x.source, "lang": x.detected_lang} for x in segs],
        "claims": [{
            "id": c.id, "quote": c.quote, "claim_en": c.claim_en, "category": c.category, "numbers": c.numbers,
            "verdict": c.verdict, "clause_id": c.clause_id, "clause_quote": c.clause_quote,
            "clause_page": c.clause_page, "explain_en": c.explain_en, "explain_local": c.explain_local,
            "ask_agent": c.ask_agent, "grounded": c.grounded, "reason": c.reason,
        } for c in claims],
        "trace": {
            "prisma_model": PRISMA_MODEL,
            "prisma": prisma,
            "evon_model": trace.get("evon_model"),
            "evon_calls": trace.get("evon_calls", []),
            "pipeline_ms": trace.get("pipeline_ms"),
            "summary_source": trace.get("summary_source"),
            "timbre": trace.get("timbre", []),
            "calls": [{"service": a.service, "request_id": a.request_id, "status": a.status,
                       "error_code": a.error_code, "latency_ms": a.latency_ms} for a in calls],
        },
        "disclaimer": DISCLAIMERS.get(case.lang, DISCLAIMER),
    }


SLIP_TEXT = {
    "hi": {"title": "लिख के दो", "intro": "विक्रेता ने ये बातें कहीं, जो पॉलिसी दस्तावेज़ में नहीं लिखी हैं या अलग लिखी हैं। कृपया इन्हें लिखित में दें।",
           "said": "कहा गया", "doc": "दस्तावेज़ में", "none": "दस्तावेज़ में इसका ज़िक्र नहीं है।",
           "agent": "विक्रेता का नाम और हस्ताक्षर", "buyer": "ग्राहक के हस्ताक्षर", "date": "तारीख़", "print": "प्रिंट करें",
           "empty": "सभी बातें दस्तावेज़ में लिखी हैं।",
           "page": "पेज", "footer": "LikhKeDo · डेमो में काल्पनिक बीमा कंपनी और कृत्रिम रिकॉर्डिंग हैं। यह वित्तीय या कानूनी सलाह नहीं है।"},
    "mr": {"title": "लिहून द्या", "intro": "विक्रेत्याने या गोष्टी सांगितल्या, ज्या पॉलिसी दस्तऐवजात लिहिलेल्या नाहीत किंवा वेगळ्या आहेत. कृपया त्या लेखी द्या.",
           "said": "सांगितले", "doc": "दस्तऐवजात", "none": "दस्तऐवजात याचा उल्लेख नाही.",
           "agent": "विक्रेत्याचे नाव व सही", "buyer": "ग्राहकाची सही", "date": "तारीख", "print": "प्रिंट करा",
           "empty": "सर्व गोष्टी दस्तऐवजात लिहिलेल्या आहेत.",
           "page": "पान", "footer": "LikhKeDo · डेमोमध्ये काल्पनिक विमा कंपनी आणि कृत्रिम रेकॉर्डिंग आहेत. हा आर्थिक किंवा कायदेशीर सल्ला नाही."},
    "ta": {"title": "எழுதிக் கொடுங்கள்", "intro": "விற்பனையாளர் சொன்ன இவை பாலிசி ஆவணத்தில் எழுதப்படவில்லை அல்லது வேறாக உள்ளன. இவற்றை எழுத்தில் தாருங்கள்.",
           "said": "சொன்னது", "doc": "ஆவணத்தில்", "none": "ஆவணத்தில் இது குறிப்பிடப்படவில்லை.",
           "agent": "விற்பனையாளர் பெயர் மற்றும் கையொப்பம்", "buyer": "வாங்குபவர் கையொப்பம்", "date": "தேதி", "print": "அச்சிடு",
           "empty": "எல்லா வாக்குறுதிகளும் ஆவணத்தில் உள்ளன.",
           "page": "பக்கம்", "footer": "LikhKeDo · டெமோவில் கற்பனைக் காப்பீட்டு நிறுவனமும் செயற்கைப் பதிவுகளும் உள்ளன. இது நிதி அல்லது சட்ட ஆலோசனை அல்ல."},
    "en": {"title": "Likh Ke Do — put it in writing", "intro": "The seller said the following, which the policy document does not state or states differently. Please confirm them in writing.",
           "said": "Said", "doc": "Document says", "none": "The document does not mention this.",
           "agent": "Seller name and signature", "buyer": "Buyer signature", "date": "Date", "print": "Print",
           "empty": "Every promise is written in the document.",
           "page": "page", "footer": "LikhKeDo · Demo uses a fictional insurer and synthetic recordings. Not financial or legal advice."},
}


def render_slip(report: dict) -> str:
    t = SLIP_TEXT.get(report.get("lang") or "en", SLIP_TEXT["en"])
    e = html.escape
    items = [c for c in report.get("claims", []) if c["verdict"] != "WRITTEN"]
    rows = []
    for i, c in enumerate(items, 1):
        doc = (f"{e(c['clause_quote'])} <span class='pg'>({e(t['page'])} {c['clause_page']})</span>"
               if c.get("clause_quote") else e(t["none"]))
        rows.append(f"<li><p><b>{e(t['said'])}:</b> “{e(c['quote'])}”</p>"
                    f"<p><b>{e(t['doc'])}:</b> {doc}</p></li>")
    body = "<ol>" + "".join(rows) + "</ol>" if rows else f"<p>{e(t['empty'])}</p>"
    today = datetime.now(timezone.utc).strftime("%d-%m-%Y")
    product = e(report.get("product_label") or "")
    return f"""<!doctype html><html lang="{e(report.get('lang') or 'en')}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(t['title'])}</title>
<style>
body{{font-family:'Noto Sans','Noto Sans Devanagari','Noto Sans Tamil',sans-serif;max-width:720px;margin:24px auto;padding:0 16px;font-size:18px;line-height:1.5;color:#111}}
h1{{font-size:28px;margin:0 0 4px}} .meta{{color:#444;font-size:15px}} li{{margin:14px 0;border-bottom:1px solid #ccc}}
.pg{{color:#555;font-size:14px}} .sig{{display:flex;gap:24px;margin-top:48px}}
.sig div{{flex:1;border-top:1px solid #000;padding-top:6px;font-size:15px}} footer{{margin-top:36px;font-size:14px;color:#444}}
button{{font-size:18px;padding:8px 16px}} @media print{{button{{display:none}}}}
</style></head><body>
<button onclick="window.print()">{e(t['print'])}</button>
<h1>{e(t['title'])}</h1><p class="meta">{product} · {e(t['date'])}: {today}</p>
<p>{e(t['intro'])}</p>{body}
<div class="sig"><div>{e(t['agent'])}</div><div>{e(t['buyer'])}</div><div>{e(t['date'])}</div></div>
<footer>{e(t['footer'])}</footer>
</body></html>"""
