# LikhKeDo — Jo bola, kya woh likha hai?

**Gnani AI Great Indian AI Internship Challenge**

## Problem (80 words)

Insurance mis-selling happens in spoken words. An agent says "returns guaranteed", "bilkul FD jaisa" or "sirf paanch saal premium"; the 40-page English policy document says the opposite, and the buyer, often an older customer in a bank branch, signs anyway. IRDAI recorded 26,667 unfair-business-practice grievances against life insurers in FY25, up about 14%. Buyers have no quick way, in their own language, to check whether what they were told is actually written in the policy before they sign.

## Target users

- Older bank customers renewing a fixed deposit who are pitched an insurance plan (Hindi/Hinglish, Marathi, Tamil).
- Their adult children, who need a shareable record and the 30-day free-look reminder.
- Later: insurer compliance teams checking sales conversations against product documents.

## Models and APIs used

- **Gnani Prisma v3.0** — streaming speech-to-text for live listening and REST for recalled promises; code-mixed output with finance keyterms.
- **Gnani Evon v3.3 (30B-A3B)** — self-hosted; extracts promises and verifies them against the policy clauses. Gnani's BF16 weights on vLLM (reasoning on for verification), or, on our ₹0 budget, the community 4-bit GGUF on llama.cpp on free Kaggle T4s, labelled "Evon v3.3 · community 4-bit GGUF (llama.cpp)" on every report. With that 4-bit build, which garbles some Hindi words, Evon picks the promises, verdicts and clauses, and the explanation, question and spoken summary are fixed sentences.
- **Gnani Timbre v3.0** — Tarika voice reads the verdict slowly, with pauses, in the buyer's language.
- Supporting: FastAPI, SQLite, pdfplumber, BM25, rapidfuzz (grounding check), React + Vite + Tailwind.

## Team contributions

- _Member 1_: _placeholder_
- _Member 2_: _placeholder_

## Project explanation (250 words)

LikhKeDo, "put it in writing", is a buyer-side check for insurance sales pitches. The buyer picks a language. In Listen mode the pitch streams to Prisma v3.0: live captions appear and phrases like "guaranteed" or "FD jaisa" light up. In Recall mode the buyer says afterwards what was promised, or types it; the seller is never recorded.

The buyer adds the policy's Customer Information Sheet, which we split into numbered clauses with page numbers. Evon v3.3, self-hosted, extracts each promise in its exact words and decides: Written, Different on paper, or Not in writing, citing the exact clause. Code then checks Evon: the promise must appear in what was said, the quote must appear in the cited clause, that clause must be on the same topic, and every number of a Written verdict must be in it. Any failure becomes "Not in writing — ask", so mistakes fall on the cautious side.

Each card shows both quotes and the page. Timbre v3.0 reads a slow summary aloud. A printable "Likh Ke Do" slip lists the promises to get in writing, and buyers who already signed see the 30-day free-look steps.

On a ₹0 budget we ran Evon as a community 4-bit build on free Kaggle GPUs. On our 30-promise answer key it scored 20/30, with no wrong "Written". Its free text garbled some Hindi, so explanations are standard sentences, labelled as such. "Under the hood" shows every Gnani request id. Fictional insurer, synthetic voices, data deleted after 24 hours. Not financial or legal advice.

## Evaluation (real numbers)

- 30 labelled promises in 5 pitches (Hindi, Tamil, Marathi, plus held-out Hindi and English written before any model run). Evon v3.3 community 4-bit GGUF (IQ4_XS): **20/30 correct**; *Written* precision **1.0** (no wrong *Written*), recall 0.6; *Different on paper* precision and recall 0.82; cited clause matches the answer key in 13/15 correct verdicts.
- By pitch: Hindi 3/6, Tamil 4/6, Marathi 3/6, held-out Hindi 4/6, held-out English 6/6. Files: `demo/eval_results_iq4xs.md` (rescore offline with `scripts/eval_answer_key.py --rescore`).
- Prisma v3.0 kept 93–95% of the pitch words from clean audio down to 5 dB babble noise and telephone-band audio (synthetic voice and noise).

## Limitations

- Evon ran only as a community 4-bit quantisation; Gnani's full BF16 model was not run (no GPU budget). Results vary between runs.
- Marathi's live run had two wrong *Different on paper* cards; it is documented but not shown as a showcase case.
- One fictional policy document; English CIS only; no OCR for scanned PDFs. Hindi/Marathi/Tamil UI text not yet reviewed by native speakers.

## Next

Run Gnani's BF16 Evon (or a Gnani-hosted endpoint) and re-run the same answer key; a larger, native-reviewed test set with real CIS layouts; OCR; a share-with-family link for the slip.
