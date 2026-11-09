"""Fixed user-facing text in the buyer's language (no model involved). Used when Evon's text is missing,
fails the script check, or was overridden by the grounding check. Never falls back to English for hi/mr/ta."""
from __future__ import annotations

# Shown when the model's explanation can't be used, keyed by the FINAL verdict.
EXPLAIN = {
    "hi": {"WRITTEN": "दस्तावेज़ में यही लिखा है।",
           "CONTRADICTED": "दस्तावेज़ में कुछ अलग लिखा है।",
           "NOT_IN_WRITING": "यह दस्तावेज़ में नहीं मिला। इसे लिखित में माँगिए।"},
    "mr": {"WRITTEN": "दस्तऐवजात हेच लिहिले आहे.",
           "CONTRADICTED": "दस्तऐवजात काहीतरी वेगळे लिहिले आहे.",
           "NOT_IN_WRITING": "हे दस्तऐवजात सापडले नाही. हे लेखी मागा."},
    "ta": {"WRITTEN": "ஆவணத்திலும் இதுவே எழுதப்பட்டுள்ளது.",
           "CONTRADICTED": "ஆவணத்தில் வேறு மாதிரி எழுதப்பட்டுள்ளது.",
           "NOT_IN_WRITING": "இது ஆவணத்தில் கிடைக்கவில்லை. இதை எழுத்தில் கேளுங்கள்."},
    "en": {"WRITTEN": "The document says the same thing.",
           "CONTRADICTED": "The document says something different.",
           "NOT_IN_WRITING": "We could not find this in the document. Ask for it in writing."},
}

ASK = {
    "hi": "क्या आप यह वादा लिखित में देंगे?",
    "mr": "हे आश्वासन तुम्ही लेखी द्याल का?",
    "ta": "இந்த வாக்குறுதியை எழுத்தில் தருவீர்களா?",
    "en": "Can you give me this promise in writing?",
}

# Category phrases for the fallback summary (the summary never quotes English claim text).
CATEGORY = {
    "hi": {"returns": "रिटर्न का वादा", "guarantee": "गारंटी का वादा", "lock_in": "lock-in का वादा",
           "premium_term": "premium कितने साल भरना है", "policy_term": "पॉलिसी की अवधि", "charges": "शुल्क",
           "liquidity": "पैसे निकालने या loan का वादा", "tax": "टैक्स का वादा", "cover": "बीमा कवर",
           "other": "एक वादा"},
    "mr": {"returns": "परताव्याचे आश्वासन", "guarantee": "हमीचे आश्वासन", "lock_in": "lock-in बद्दलचे आश्वासन",
           "premium_term": "premium किती वर्षे भरायचा", "policy_term": "पॉलिसीचा कालावधी", "charges": "शुल्क",
           "liquidity": "पैसे काढणे किंवा loan चे आश्वासन", "tax": "करासंबंधी आश्वासन", "cover": "विमा संरक्षण",
           "other": "एक आश्वासन"},
    "ta": {"returns": "வருமானம் பற்றிய வாக்குறுதி", "guarantee": "உத்தரவாதம் பற்றிய வாக்குறுதி",
           "lock_in": "lock-in பற்றிய வாக்குறுதி", "premium_term": "premium எத்தனை ஆண்டுகள் கட்ட வேண்டும்",
           "policy_term": "பாலிசி காலம்", "charges": "கட்டணங்கள்",
           "liquidity": "பணம் எடுப்பது அல்லது loan பற்றிய வாக்குறுதி", "tax": "வரி பற்றிய வாக்குறுதி",
           "cover": "காப்பீட்டுத் தொகை", "other": "ஒரு வாக்குறுதி"},
    "en": {"returns": "the promise about returns", "guarantee": "the guarantee", "lock_in": "the lock-in promise",
           "premium_term": "how many years of premium", "policy_term": "the policy term", "charges": "the charges",
           "liquidity": "the withdrawal or loan promise", "tax": "the tax promise", "cover": "the life cover",
           "other": "a promise"},
}

SUMMARY = {
    "hi": "<slow> {n} में से {k} बातें काग़ज़ पर अलग हैं या लिखी नहीं हैं। <pauses> सबसे ज़रूरी: {top}। <pauses> साइन करने से पहले इसे लिखित में माँगिए।",
    "mr": "<slow> {n} पैकी {k} गोष्टी कागदावर वेगळ्या आहेत किंवा लिहिलेल्या नाहीत। <pauses> सर्वात महत्त्वाचे: {top}। <pauses> सही करण्यापूर्वी हे लेखी मागा।",
    "ta": "<slow> {n} வாக்குறுதிகளில் {k} ஆவணத்தில் வேறாக உள்ளன அல்லது எழுதப்படவில்லை. <pauses> முக்கியமானது: {top}. <pauses> கையெழுத்திடும் முன் இதை எழுத்தில் கேளுங்கள்.",
    "en": "<slow> {k} of {n} promises are different on paper or not written at all. <pauses> Most important: {top}. <pauses> Ask for it in writing before you sign.",
}

ALL_WRITTEN = {
    "hi": "<slow> सभी {n} बातें दस्तावेज़ में लिखी हैं। <pauses> फिर भी साइन करने से पहले दस्तावेज़ ध्यान से पढ़िए।",
    "mr": "<slow> सर्व {n} गोष्टी दस्तऐवजात लिहिलेल्या आहेत। <pauses> तरीही सही करण्यापूर्वी दस्तऐवज नीट वाचा।",
    "ta": "<slow> எல்லா {n} வாக்குறுதிகளும் ஆவணத்தில் உள்ளன. <pauses> இருந்தாலும் கையெழுத்திடும் முன் ஆவணத்தைக் கவனமாகப் படியுங்கள்.",
    "en": "<slow> All {n} promises are written in the document. <pauses> Still, read the document carefully before you sign.",
}

NO_PROMISES = {"hi": "कोई वादा नहीं मिला।", "mr": "कोणतेही आश्वासन सापडले नाही।",
               "ta": "எந்த வாக்குறுதியும் கிடைக்கவில்லை.", "en": "No promises were found."}

DISCLAIMER = {"hi": "यह वित्तीय या कानूनी सलाह नहीं है।", "mr": "हा आर्थिक किंवा कायदेशीर सल्ला नाही.",
              "ta": "இது நிதி அல்லது சட்ட ஆலோசனை அல்ல.", "en": "Not financial or legal advice."}

# Reason codes set by the grounding check (localized in the frontend i18n map as rsn_<code>).
REASONS = ("quote_not_in_transcript", "clause_quote_not_found", "clause_off_topic", "number_missing", "invalid_model_output")


def fallback_summary(lang: str, verdicts: list[tuple[str, str]]) -> str:
    """verdicts: [(verdict, category)]. Picks CONTRADICTED first, then NOT_IN_WRITING."""
    if not verdicts:
        return NO_PROMISES[lang]
    bad = [v for v in verdicts if v[0] == "CONTRADICTED"] + [v for v in verdicts if v[0] == "NOT_IN_WRITING"]
    if not bad:
        return ALL_WRITTEN[lang].format(n=len(verdicts))
    cats = CATEGORY[lang]
    return SUMMARY[lang].format(n=len(verdicts), k=len(bad), top=cats.get(bad[0][1], cats["other"]))
