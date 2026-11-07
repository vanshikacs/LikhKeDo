# LikhKeDo — project rules for Claude Code

## What we are building
LikhKeDo ("put it in writing"): a web app that hears an insurance/bank sales pitch (Hindi, Hinglish,
Tamil, Marathi, English), extracts each spoken promise, checks it against the policy's Customer
Information Sheet (CIS), and returns per-promise verdicts WRITTEN / CONTRADICTED / NOT_IN_WRITING,
with both exact quotes, plus a spoken summary in the buyer's language.
Contest: Gnani AI Great Indian AI Internship Challenge. Deadline 10 Nov 2026 23:59 IST. Demo-first.

## Stack (do not add frameworks)
- Backend: Python 3.11, FastAPI, uvicorn, httpx, websockets, pydantic v2, pydantic-settings,
  sqlmodel (SQLite), pdfplumber, rank-bm25, rapidfuzz, openai (client for Evon), pytest.
- Frontend: React + Vite + TypeScript + Tailwind. No UI kit beyond Tailwind. No state library.
- Deploy: backend on Render (Docker), frontend on Vercel. Evon on a rented GPU with vLLM.

## Gnani APIs (from docs.gnani.ai; never invent fields)
- Auth header on every call: X-API-Key-ID: <GNANI_API_KEY>. Base REST https://api.vachana.ai,
  WS wss://api.vachana.ai.
- Prisma REST: POST /stt/v3, multipart: audio_file, model=prisma-v3.0, language_code
  (e.g. "hi-IN,en-IN" or "indic-auto"), format=codemix, keyterms (JSON array string, <=200),
  topic (<=1600 chars), previous_text. Max 30 s audio per request. Response: success, request_id,
  transcript, model, detected_language_code, processing_time, end_to_end_latency.
- Prisma streaming: wss://api.vachana.ai/stt/v3/stream. Handshake headers: x-api-key-id, model,
  language_code, x-sample-rate (16000), format, keyterms, x-idle-timeout-sec. Send binary PCM16 mono
  frames of exactly 1024 bytes every 32 ms; send {"type":"commit"} to finish. Server messages:
  connected, speech_start, processing, transcript {text, segment_index, detected_language_code,
  latency}, error. Session max 15 min.
  MEASURED: streaming language_code must be exactly ONE locale ("hi-IN"); "hi-IN,en-IN" -> error + 1008.
  REST accepts "hi-IN,en-IN". Timbre v3.0 returns WAV with 0xFFFFFFFF sizes (patch the header).
- Timbre REST: POST /api/v1/tts/inference, JSON {text, voice, model, language, speed, audio_config
  {sample_rate, num_channels, sample_width, encoding:"linear_pcm", container:"wav"}} -> raw audio/wav.
  Primary: model "timbre-v3.0", voice "Tarika". Fallback: model "timbre-v2.5", voice "Poorvi",
  language "hi-en". v3.0 supports inline tags <slow> <pauses>; v2.5 strips them.
- Errors: 429 RATE_LIMITED (account may allow ONE active request at a time), 402 no credit,
  504 UPSTREAM_TIMEOUT. Retry only 429/500/503/504 with backoff 0.5, 1, 2 s. Never retry other 4xx.
- ALL Gnani calls go through GnaniGate (one asyncio.Lock) in backend/app/gnani.py. No exceptions.
- Cache: Prisma results by sha256(audio bytes + params); Timbre by sha256(text+voice+model+lang).

## Evon (self-hosted)
- OpenAI-compatible endpoint at EVON_BASE_URL with EVON_API_KEY, model
  "gnani/gnani-evon-v3.3-30B-A3B". temperature 0.6, top_p 0.95.
- Extraction: extra_body={"chat_template_kwargs":{"enable_thinking":false}}, max_tokens 2048.
- Verification: enable_thinking true, max_tokens 4096. Use only message.content (never show
  reasoning to users).
- Always name the output language AND script in the system prompt. Validate JSON with Pydantic;
  one repair retry; otherwise mark the claim NOT_IN_WRITING.
- NEVER substitute another LLM (Gemini/OpenAI/Claude). If Evon is down, serve cached demo results
  and say so in the UI.

## Non-negotiable product rules
- Grounding check in code: claim.quote must fuzzy-match the transcript (rapidfuzz partial_ratio >= 90)
  and clause_quote must match the clause text the same way; numbers in a WRITTEN verdict must appear
  in the clause. Failing checks downgrade the verdict to NOT_IN_WRITING.
- Language: say "verify" / "ask for it in writing", never "the agent lied". Every report shows
  "Not financial or legal advice".
- Synthetic data only. Fictional insurer "Bharosa Life", product "Suraksha Plus Guaranteed Wealth Plan".
  No real names, phone numbers, account numbers, Aadhaar, PAN.
- Privacy: never write raw audio to disk in production; case data expires after 24 h; no transcript
  text in logs. Log Gnani request_id, status, latency.
- Keys only from environment variables. Never print or commit them.

## Working style
- Make the smallest change that completes the current phase. Don't refactor unrelated code.
- After each change, run the relevant tests (pytest -q in backend, npm run build in frontend) and
  report results honestly. If something is unverified against the real API, say so.
- Ask before adding a dependency not listed above.
- Keep this file short; put long notes in README.md.
