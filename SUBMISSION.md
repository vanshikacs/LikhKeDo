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
- **Gnani Evon v3.3 (30B-A3B)** — self-hosted; extracts promises and verifies them against the policy clauses. Gnani's BF16 weights on vLLM (reasoning on for verification), or, on our ₹0 budget, the community 4-bit GGUF on llama.cpp on free Kaggle T4s, labelled "Evon v3.3 · community 4-bit GGUF (llama.cpp)" on every report.
- **Gnani Timbre v3.0** — Tarika voice reads the verdict slowly, with pauses, in the buyer's language.
- Supporting: FastAPI, SQLite, pdfplumber, BM25, rapidfuzz (grounding check), React + Vite + Tailwind.

## Team contributions

- _Member 1_: _placeholder_
- _Member 2_: _placeholder_

## Project explanation (250 words)

LikhKeDo, "put it in writing", is a buyer-side check for sales pitches. The buyer opens it on a phone and picks a language. In Listen mode, the pitch streams to Prisma v3.0, live captions appear, and phrases like "guaranteed" or "FD jaisa" light up as red flags. In Recall mode, the buyer simply says afterwards what they were promised, so the seller never has to be recorded.

The buyer then adds the policy's Customer Information Sheet. We split it into numbered clauses with page numbers. Evon v3.3, on our self-hosted server, extracts every promise with its exact words, retrieves the most relevant clauses, and decides for each promise: Written, Contradicted, or Not in writing. Code then checks Evon's work: the quoted promise must appear in the transcript, the quoted clause in the document, and every number of a "Written" verdict in that clause. Any failure turns the card into "Not in writing — ask", so errors fall on the cautious side.

The report shows both quotes side by side, the page number, and a polite question to ask. Timbre v3.0 reads a slow summary aloud in Hindi, Marathi, Tamil or English. A printable "Likh Ke Do" slip lists the unwritten promises for the seller to sign, and buyers who already bought see the 30-day free-look steps.

Every Gnani request id and latency is visible in an "Under the hood" panel, and a badge says what produced each report: live Evon, a rules check with no AI model, or a case saved from a live run. The demo uses a fictional insurer and synthetic voices; nothing is stored beyond 24 hours. Not financial or legal advice.
