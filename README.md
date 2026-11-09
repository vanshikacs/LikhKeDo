# LikhKeDo — *Jo bola, kya woh likha hai?*

**LikhKeDo ("put it in writing") listens to an insurance or bank sales pitch in Hindi, Hinglish, Tamil, Marathi or English, pulls out every spoken promise, checks each one against the policy's Customer Information Sheet, and tells the buyer — out loud, in their language — which promises are written, which the document contradicts, and which they should ask to get in writing.**

Built for the Gnani AI Great Indian AI Internship Challenge on Gnani's stack: Prisma (speech-to-text), Evon (reasoning, self-hosted) and Timbre (text-to-speech). Demo data is fictional. **Not financial or legal advice.**

**Solution pitch (1 page):** [LikhKeDo_Solution_Pitch.pdf](LikhKeDo_Solution_Pitch.pdf) · **Demo video:** [Google Drive](https://drive.google.com/file/d/1Vqq8F3QxL4IrpMzwWsv_9mKK5YpC1n4Q/view)

**Try it:** [likh-ke-do.vercel.app](https://likh-ke-do.vercel.app) · Android app: [LikhKeDo.apk](https://github.com/vanshikacs/LikhKeDo/raw/main/LikhKeDo.apk) ([details](android/README.md))

## The problem

Mis-selling is the single largest category of life-insurance complaints in India. IRDAI recorded **26,667 "unfair business practice" grievances against life insurers in FY25, up about 14%**, or 22% of all life-insurance complaints ([Outlook Money, reporting the IRDAI annual report](https://www.outlookmoney.com/personal-finance/insurance-claims-mis-selling-account-for-most-insurance-complaints-in-fy25-reveals-irdai-annual-report)). The pattern is familiar: "bilkul FD jaisa", "returns guaranteed", "sirf paanch saal premium". The promise is spoken; the 40-page English document says something else; the buyer, often older, signs anyway.

## How it works (30 seconds)

1. **Hear** — *Listen* mode streams the pitch live (Prisma v3.0 streaming, code-mixed, finance keyterms) and lights up red-flag phrases. *Recall* mode lets the buyer say afterwards what they were told (Prisma v3.0 REST) — no recording of the seller needed — or **type / paste** the words (no microphone needed; no Gnani call).
2. **Read** — the policy PDF becomes numbered clauses with page numbers (pdfplumber + BM25).
3. **Check** — Evon v3.3 extracts each promise with its exact quote, then compares it with the policy and returns WRITTEN / CONTRADICTED / NOT_IN_WRITING with the exact clause quote. On vLLM (BF16): one call per promise with the top clauses, reasoning on. On the community 4-bit GGUF (llama.cpp): all promises in one call, thinking off, to stay under the tunnel's 100 s limit.
4. **Ground** — code, not the model, has the last word: the promise quote must appear in the transcript, the clause quote must appear in the cited clause, the cited clause must be about the same topic as the promise (BM25 rank in the more relevant half of the document), and every number in a WRITTEN verdict must be in that clause. Anything that fails becomes *Not in writing — ask*, with the reason shown on the card.
5. **Speak** — Timbre v3.0 (Tarika) reads a slow summary with pauses in the buyer's language. One tap prints a *Likh Ke Do* slip for the seller to sign, and explains the 30-day free look.

> **What is model output and what is not.** Evon picks the promises, each verdict and the cited clause. With the community 4-bit GGUF we ran, its free text was unreliable (garbled Hindi words, explanations the clause did not support), so on that engine the explanation, the question to ask and the spoken summary are **standard sentences per verdict** in each language. Each card and the summary say so on screen, and *Under the hood* shows it. With BF16 Evon on vLLM the explanations come from the model and pass a script check.

```mermaid
flowchart LR
  subgraph Browser["React + Vite + Tailwind (Vercel)"]
    MIC["Mic → AudioWorklet\n16 kHz PCM16, 1024-byte frames"]
    REC["Recall clip ≤ 30 s / policy PDF"]
    UI["Captions · red flags · verdict cards · audio · slip"]
  end
  subgraph API["FastAPI (Render)"]
    WSP["WS proxy"]
    GATE["GnaniGate\none lock · retry 0.5/1/2 s"]
    ING["PDF → clauses · BM25"]
    PIPE["extract → retrieve → verify → ground-check"]
    DB[("SQLite · 24 h TTL")]
  end
  subgraph Gnani["Gnani APIs"]
    PS["Prisma v3.0 streaming"]
    PR["Prisma v3.0 REST"]
    TB["Timbre v3.0"]
  end
  EV["Evon v3.3\nBF16 on vLLM, or community\n4-bit GGUF on llama.cpp (Kaggle)"]
  MIC --> WSP --> GATE --> PS
  REC --> GATE --> PR
  REC --> ING --> DB
  PIPE <--> EV
  PIPE <--> DB
  PIPE --> GATE --> TB
  PS --> WSP --> UI
  PIPE --> UI
```

## Languages

| Language | Status |
| --- | --- |
| Hindi / Hinglish | Public showcase case (saved live run), full UI, Timbre voice verified |
| Tamil (+ English) | Public showcase case (saved live run), full UI, Timbre voice verified |
| English | Full UI; held-out evaluation pitch 6/6 on the 4-bit engine |
| Marathi | Full UI and Timbre voice work, but its live run had two wrong *Different on paper* cards, so it is **not** in the public showcase and the app warns when Marathi is selected |

UI strings in Hindi, Marathi and Tamil were drafted by us and have **not** been reviewed by native speakers.

## Gnani models and exactly how we use them

| Model | Where | How |
| --- | --- | --- |
| **Prisma v3.0 streaming** | Listen mode | `wss://api.vachana.ai/stt/v3/stream`, `format=codemix`, `language_code="<lang>,en-IN"`, 21 finance keyterms, 1024-byte PCM16 frames every 32 ms, `commit` on stop ([backend/app/stream_proxy.py](backend/app/stream_proxy.py)) |
| **Prisma v3.0 REST** | Recall mode, demo seeding | `POST /stt/v3`, codemix + keyterms + topic; clips over 28 s split on silence with `previous_text` ([backend/app/gnani.py](backend/app/gnani.py)) |
| **Evon v3.3 (30B-A3B)** | Extraction + verification | Self-hosted, OpenAI-compatible. **vLLM (BF16):** extraction thinking off (2,048 tokens), verification per promise thinking on (4,096 tokens). **llama.cpp (community 4-bit GGUF, used for our runs):** one request at a time, thinking off, one batched verification call; an invalid item in the batch is re-checked alone. Only `message.content` is used; language **and script** named in every prompt; Pydantic validation with one repair retry ([backend/app/evon.py](backend/app/evon.py), [prompts.py](backend/app/prompts.py)) |
| **Timbre v3.0** | Spoken summary, per-promise audio, consent announcement | Voice Tarika with `<slow>` and `<pauses>`; fallback combination on HTTP 400; cached by text hash so each sentence is paid for once |

All Gnani calls pass through one `asyncio.Lock` (the account may allow one active request); 429/500/503/504 retry after 0.5, 1 and 2 s; every call is logged with its request id, status and latency, and the report's **Under the hood** panel shows them. No other LLM is called anywhere.

## Three modes, always labelled

| Mode | What runs | Badge on the report |
|---|---|---|
| **A** | Prisma + Timbre + Evon (BF16 on vLLM, or the community 4-bit GGUF on llama.cpp for ₹0, see [EVON_FREE.md](EVON_FREE.md)) | `Live check · <engine label>` |
| **B** | Prisma + Timbre; promises checked by plain keyword and number rules when Evon is down and the user chooses it | `Rules check — no AI model` |
| **C** | Results saved from a real mode-A run, served when no Evon server is up | `Saved from a live check — <date>` |

No other LLM is ever used in place of Evon.

## Measured API behaviour

Measured on 7 Nov 2026 with `scripts/smoke_timbre.py`, `smoke_prisma.py`, `concurrency_probe.py` and `try_gnani_client.py`, on an 11 s Hindi/Hinglish pitch clip (the clip itself was synthesised with Timbre). Evon numbers come after the GPU is up.

| Item | Result |
| --- | --- |
| Prisma v3.0 REST, 11.0 s clip, `hi-IN,en-IN`, codemix + keyterms | HTTP 200, detected `hi-IN`, processing 0.22–0.25 s, wall 0.7–1.1 s |
| Codemix output | English finance words stay Latin ("FD", "returns guaranteed", "premium"); small numbers come back as words ("बारह percent", "पाँच साल") |
| Prisma v3.0 streaming | `language_code` must be **one** locale (`hi-IN`); `hi-IN,en-IN` returns an error and closes with 1008. Connected 0.4 s, `speech_start` 0.7 s, transcript 0.3 s after `commit` (server latency ~225 ms) |
| Timbre v3.0, Tarika, `hi-IN`, speed 0.9, 24 kHz | HTTP 200 on the first combination; 136 chars → 11.0 s audio in 2.8 s. WAV header sizes are `0xFFFFFFFF` (streaming style); we patch them |
| Timbre v3.0, Tarika, Hindi / Tamil / Marathi pitches (~900 chars each, 2 chunks) | All HTTP 200 on the first combination: 57.0 s / 51.3 s / 54.5 s of audio in 9.1 / 9.5 / 8.7 s (`scripts/make_pitch_audio.py`) |
| Round trip: Timbre pitch audio → Prisma REST (3 chunks ≤ 30 s each) | Detected `hi-IN` / `ta-IN` / `mr-IN`; transcript vs. source text similarity 93 / 92 / 95 % (rapidfuzz ratio). So Tarika is intelligible in Tamil and Marathi |
| Browser stream through our proxy (11 s clip) | 1024-byte frames paced at 32 ms, 0 Prisma errors; the saved debug WAV transcribed over REST matches the live caption word for word |
| Does an open stream block Timbre? | **No**: Timbre returned 200 in 0.94 s while a stream was open, so streams don't hold GnaniGate (`STREAM_HOLDS_LOCK=false`) |
| Request ids | Gnani echoes our `X-API-Request-ID` as `request_id`, so the ids in **Under the hood** match Gnani's logs |
| Credits per Prisma call / per Timbre call | _check the balance on app.gnani.ai before and after a call_ |
| Evon latency (community 4-bit GGUF IQ4_XS, 2× Kaggle T4, via Cloudflare tunnel, 9 Nov) | 3–5 s per call; 17–65 s for a whole 6-promise pitch (one batched verification call) |

## Accuracy

`scripts/eval_answer_key.py` runs the pipeline on three fictional pitches (Hindi/Hinglish, Tamil+English, Marathi; 6 promises each: 2 written, 2 contradicted, 2 not in writing) against the fictional CIS and writes [demo/eval_results.md](demo/eval_results.md).

The answer key now has **30 labelled promises** in 5 pitches. Two of them (`hi_hinglish_2`, `en_english`: 12 promises on lock-in, bonus, charges, premium amount, surrender, claims) were written *after* the rules check, with their expected verdicts fixed before any run, so they are a held-out test.

| Mode B (rules, no AI model) | Original 3 pitches (rules written with them in view) | Held-out 2 pitches |
| --- | --- | --- |
| On the pitch text | 18/18 | **2/12**; one wrong *Written* ("returns fixed at 8 percent" matched the illustrated 8%) |
| After one post-hoc safety fix (an illustrated rate is never *Written*) | 18/18 | 2/12, no wrong *Written* or *Different on paper* |
| On Prisma v3.0 transcripts of the Timbre audio | 15/18 | 1/12 (English numbers come back as words) |

So keyword rules don't generalise: they are a labelled fallback that errs towards "ask for it in writing", not a substitute for Evon. Files: [demo/eval_rules.md](demo/eval_rules.md), [demo/eval_rules_stt.md](demo/eval_rules_stt.md), [demo/eval_rules_heldout_before_fix.md](demo/eval_rules_heldout_before_fix.md).

**Mode A, Evon v3.3 · community 4-bit GGUF (IQ4_XS on llama.cpp), 9 Nov, pitch text, all 30 promises:** two runs of the current code: **20/30** ([demo/eval_results_iq4xs.md](demo/eval_results_iq4xs.md)) and **18/30** ([demo/eval_results_iq4xs_run2.md](demo/eval_results_iq4xs_run2.md)); an earlier run before the fixes scored 19/30. **No wrong *Written* in any run** (precision 1.0; recall 0.6 and 0.5). *Different on paper* is less reliable: precision 0.82 in the first run but 0.53 in the second (7 wrong red cards). Results vary between runs (temperature 0.6). This 4-bit file drops tokens in Hindi even at temperature 0, so on this engine the cards show fixed sentences for the explanation, the question and the spoken summary; Evon still extracts the promises and picks each verdict and clause. Gnani's full BF16 Evon was not run (no GPU budget). Details: [EVON_FREE.md](EVON_FREE.md).

By pitch (run 1 / run 2): Hindi 3/6 · 5/6, Tamil 4/6 · 2/6, Marathi 3/6 · 3/6, held-out Hindi 4/6 · 2/6, held-out English 6/6 · 6/6. For correct *Written* / *Different on paper* verdicts, the cited clause was the answer key's clause in **13/15** and **12/13**; the others cited a related clause (the charges table for the premium term; surrender charges instead of lock-in).

One more unseen pitch, written with its expected verdicts fixed before the run (6 promises: policy term, premium amount, "16 lakh guaranteed", withdrawal after 5 years with no charge, no medical check-up, "best plan"): **4/6**. One wrong red card: "premium only ₹1 lakh a year" was judged against the premium *term* (10 years) instead of the premium amount clause (Rs 1,00,000). Recompute without the model: `scripts/eval_answer_key.py --rescore demo/eval_results_iq4xs.json`. The answer key was written before any model run and has not been changed.

Main failure patterns: Evon sometimes compares a promise with the wrong clause on a related topic (premium amount vs premium term, policy term vs premium term) and calls it *Different on paper*, a quoted, real clause, so the code checks cannot catch it; "better than FD" (an opinion) is usually not extracted at all; the ₹10 lakh cover is sometimes judged *Not in writing* although the clause says Rs 10,00,000; the 0% loan is sometimes *Different on paper* citing the returns clause (the document has no loan clause); quotes slightly altered by the model are rejected by the grounding check.

## Noise robustness

`scripts/noise_test.py` mixes background noise at 20, 10 and 5 dB SNR plus an 8 kHz telephone band, and compares Prisma v2.5 (verbatim) with v3.0 (codemix + keyterms). Run on 7 Nov 2026 on the Hindi pitch (Timbre audio) with synthetic noise from `scripts/make_noise.py` (two other pitches talking over each other, and pink noise), scored with the rules check because Evon was not up ([demo/noise_results.md](demo/noise_results.md)):

| Prisma | clean | 20 dB | 10 dB | 5 dB | telephone 8 kHz |
| --- | --- | --- | --- | --- | --- |
| v3.0 codemix + keyterms: similarity to script / correct verdicts (of 6) | 94% · 4 | 95% · 5 | 94% · 4 | 93% · 5 | 93% · 4 |
| v2.5 verbatim | 72% · 0 | 72% · 0 | 72% · 0 | 72% · 0 | 72% · 0 |

v3.0 holds steady from clean audio down to 5 dB babble and telephone-band audio. v2.5 writes everything in Devanagari ("भरोसा लाइफ", "एफ डी"), so it scores lower by construction against a mixed-script script and our keyword rules; that row shows why we use codemix, not that v2.5 hears worse. Caveats: a clean synthetic voice is easier than a real one, and the noise is synthetic. Real-room recordings are still to do.

Live captions, end to end: `scripts/stream_pitch_test.py` streams each pitch through our WebSocket proxy to Prisma at real time, exactly like the browser. Caption similarity to the script: Hindi 96%, Tamil 92%, Marathi 94%, with the red flags firing. One Tamil run was closed by Prisma with code 1012 (service restart); the proxy now reconnects transparently on 1006/1011/1012/1013.

## Demo cases

Saved on 9 Nov from one live run each (Prisma REST on the Timbre pitch audio → Evon 4-bit GGUF → Timbre), served at `/api/demo` with the badge *Saved from a live check*. They open without any GPU running. Compared with the answer key:

| Case | Right | Wrong or missed |
| --- | --- | --- |
| Hindi / Hinglish | returns guaranteed → *Different on paper*; 5-year premium → *Different on paper*; ₹10 lakh cover → *Written*; 0% loan → *Not in writing* | 30-day free look extracted as a fragment ("returns कर सकते हैं") → *Not in writing*; "better than FD" not extracted; one misquoted promise rejected by the grounding check |
| Tamil + English | returns → *Different on paper*; ₹10 lakh cover → *Written*; 30-day free look → *Written*; loan → *Not in writing* | 5-year premium → *Not in writing* (Evon altered the quote, so the grounding check rejected it); "better than FD" not extracted |
| Marathi (**kept in the repo, not served**: `HELD_BACK` in [backend/app/routes/demo.py](backend/app/routes/demo.py)) | returns and 5-year premium → *Different on paper* | loan and 30-day free look wrongly *Different on paper* (cited the returns clause / the free-look clause); cover → *Not in writing*; "better than FD" not extracted |

## Honest limitations

- The demo policy, insurer ("Bharosa Life Insurance Ltd (FICTIONAL)") and recordings are synthetic. Real CIS documents vary; scanned PDFs are rejected (no OCR).
- Evon runs only while a GPU session is up (free: the community 4-bit GGUF on Kaggle T4s; the IQ4_XS file we ran garbles some Hindi words, so its free text is replaced by fixed sentences; paid: BF16 on vLLM, not run). The rest of the time the public site serves cases saved from a live run and says so (`DEMO_ONLY=true`).
- Code-mixed speech recognition can mishear numbers ("baarah" vs "barah"); the grounding check prefers *Not in writing — ask* over a wrong red card, so errors fall on the cautious side.
- The answer key is small (30 promises); it shows the pipeline works, not production accuracy. The saved demo cases are single live runs and include mistakes (see *Demo cases* below).
- Hindi, Marathi and Tamil UI strings were drafted by us and need native review.
- The demo CIS is in English, so the *document* quote on each card stays in English even in a Hindi, Marathi or Tamil report (it must be the exact words of the document). Everything else on the card is in the buyer's language; the model's English paraphrase sits behind a "Show English" toggle.
- Live Listen mode records nothing to disk, but everyone present should still know the conversation is being noted.

## Recording the demo

Full recording, posting and submission plan: [LAUNCH.md](LAUNCH.md).

1. Backend with `DEBUG_SAVE_AUDIO=true` (dev only), frontend `npm run dev`, Evon up (`/api/health` shows `"evon":"ok"`).
2. Open `http://localhost:5173/?record=1`: a phone-width column with larger type, and cards that highlight as they appear.
3. Live pitch: a second person reads `demo/pitches/hi_hinglish.txt` into the mic. Or, on `/dev/listen`, use **Start + play pitch audio**, which plays the Timbre pitch from the speakers with echo cancellation off (otherwise the browser cancels the very audio it is meant to capture).
4. Record mic audio, not system audio. `?record=0` turns recording mode off.

## Prior art and how we differ

- **Saakshi** ([lablab.ai hackathon, Sep 2026](https://lablab.ai/submissions/yq8ij2120upfm8wq4mztpj2x)) — seller-side consent proof for advisors' disclosures, on a non-Gnani stack. Same insight (the mis-sale is in the sentence); LikhKeDo serves the *buyer*, in Indic voice, on Gnani.
- **Insurer-side call-vs-document checks** (e.g. the [NuSummit case study](https://www.nusummit.com/?p=53048)) and pre-issuance verification calls compare agent conversations with policy terms inside one insurer. LikhKeDo does the same check for the person being sold to, before they sign.

## Privacy and synthetic data

No accounts, no names, phone numbers, account numbers, Aadhaar or PAN are requested. Raw audio is never written to disk (streamed and discarded; recall clips are processed in memory). Case data is deleted after 24 hours or on *Delete my data*, and so are cached transcripts and synthesized audio. Typed words are stored like transcripts and deleted on the same schedule. Logs hold request ids, status and latency — never transcript text. To protect the Gnani credit on a public deployment, each visitor gets at most 3 checks, 20 recall clips and 6 live listening sessions per hour (`ANALYSES_PER_HOUR`, `RECALLS_PER_HOUR`, `LISTENS_PER_HOUR`). LikhKeDo is an informational comparison tool: it is not financial or legal advice, not affiliated with any insurer, and not an IRDAI service. Every person, insurer and policy in the demo is fictional; the demo pitch audio is synthesized with Timbre and the test noise is generated, so no real person's voice is used.

## Run locally

```bash
python -m venv backend/.venv
backend/.venv/Scripts/pip install -r backend/requirements.txt      # macOS/Linux: backend/.venv/bin/pip
cd frontend && npm install && cd ..
cp .env.example .env                                               # add GNANI_API_KEY etc.
```

| Task | With make | Without make (Windows PowerShell) |
| --- | --- | --- |
| Backend dev server | `make dev-backend` | `cd backend; .venv\Scripts\python -m uvicorn app.main:app --reload --port 8000` |
| Frontend dev server | `make dev-frontend` | `cd frontend; npm run dev` |
| Backend tests | `make test` | `cd backend; .venv\Scripts\python -m pytest -q` |
| Frontend build (+ translation check) | | `cd frontend; npm run build` |
| Accuracy (needs Evon) / offline rescore | | `scripts\eval_answer_key.py` / `scripts\eval_answer_key.py --rescore demo\eval_results_iq4xs.json` |
| Demo cases (live run only; needs Evon) | | `backend\.venv\Scripts\python scripts\seed_demo.py` |

Uploads go as raw request bodies (`audio/wav`, `application/pdf`) rather than multipart, so the backend needs no extra form-parsing dependency. Deployment: see [DEPLOY.md](DEPLOY.md).

## Team

_Placeholder: names and contributions._
