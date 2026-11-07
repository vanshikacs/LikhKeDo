# Running Evon for ₹0

Gnani's full-precision Evon v3.3 (BF16, 63.5 GB of weights) needs an 80 GB GPU, which costs money. Gnani has no confirmed hosted Evon API for participants yet (we have asked on Discord). LikhKeDo therefore supports three ways of running, and every report says which one produced it.

| Mode | What runs | When | Label shown in the app |
|---|---|---|---|
| **A · live** | Prisma + Timbre (Gnani API) + Evon | While an Evon server is up | `Live check · <engine label>` |
| **B · rules** | Prisma + Timbre live; promises checked by plain keyword and number rules | Evon is down and the user chooses it, or `EVON_PROVIDER=none` | `Rules check — no AI model` |
| **C · saved** | Results saved from a real mode-A run (`scripts/seed_demo.py`) | Public site the rest of the time (`DEMO_ONLY=true`) | `Saved from a live check — <date>` + engine label |

Mode B is never called Evon or AI. It never invents an English paraphrase, and it uses the same code-level grounding check as mode A. No other LLM is ever substituted for Evon.

## The free Evon: community 4-bit GGUF on Kaggle

- Weights: [luminenio/gnani-evon-v3.3-30B-A3B-GGUF](https://huggingface.co/luminenio/gnani-evon-v3.3-30B-A3B-GGUF), file `Q4_K_M` (~24.7 GB), converted from Gnani's BF16 release. **Access must be requested on that page** and approved by the maintainer.
- It is genuinely Evon, but not Gnani's full-precision release. The quality loss from 4-bit quantisation has not been measured; the maintainer tested it lightly (Hindi and English, 2,048-token context, thinking off).
- Label everywhere: **"Evon v3.3 · community 4-bit GGUF (llama.cpp)"**. This is the default `EVON_LABEL` for `EVON_PROVIDER=llamacpp`.

### Steps

1. Request access on the GGUF page. Verify your phone number in Kaggle settings (needed for GPUs and internet).
2. Create a Kaggle notebook from [kaggle/evon_server.ipynb](kaggle/evon_server.ipynb). Settings: Accelerator **GPU T4 x2**, Internet **on**. Add-ons → Secrets: `HF_TOKEN`, `EVON_API_KEY` (any long random string).
3. Run all cells (first run: ~10 min to build llama.cpp, then the 24.7 GB download, then a few minutes to load). The last cell prints the lines for your `.env`:
   ```
   EVON_PROVIDER=llamacpp
   EVON_BASE_URL=https://<random>.trycloudflare.com/v1
   EVON_MODEL=evon
   EVON_QUANT=Q4_K_M
   EVON_TIMEOUT=90
   EVON_API_KEY=<same value as the Kaggle secret>
   ```
4. On your laptop: `backend\.venv\Scripts\python scripts\smoke_evon.py`. Test 4 runs the real pipeline on the demo pitch and warns if any call gets close to 100 s.
5. Restart the backend; `http://localhost:8000/api/health` should show `"evon":"ok"`.
6. In the same session: `scripts\eval_answer_key.py` (accuracy), `scripts\seed_demo.py` (saved demo cases, mode C), and record the video.
7. **Stop the Kaggle session** when done, then set `DEMO_ONLY=true` on the public deployment.

### How LikhKeDo adapts in `llamacpp` mode

| Constraint | What the code does |
|---|---|
| Cloudflare quick tunnels cut each request at 100 s | `EVON_TIMEOUT=90`; all claims are verified in **one** call (one JSON array) instead of one call per claim |
| `llama-server -np 1` has one slot | A process-wide lock sends one request at a time |
| Thinking makes answers long and slow | Thinking is off for every call (`enable_thinking: false` plus "Return ONLY JSON" in the prompt); any `<think>` text that leaks into the content is stripped; reasoning is never shown |
| 4-bit output can be less reliable | Pydantic validation, one repair retry, then `NOT_IN_WRITING`; the code-level grounding check (quotes ≥ 90 fuzzy match, numbers present in the clause) is unchanged |

### Limits

- Around 30 GPU-hours a week and sessions of up to about 12 hours on Kaggle; the tunnel URL changes every session.
- Speed on two T4s is unmeasured until the first run; `smoke_evon.py` reports it.
- Kaggle's terms may restrict running servers from notebooks. Use this only for your own testing and for recording the demo.

## Measured so far

| Test | Result |
|---|---|
| Mode B on the pitch text (the rules were written with these pitches in view, so this is not a fair accuracy test) | 18/18 — [demo/eval_rules.md](demo/eval_rules.md) |
| Mode B on real Prisma v3.0 transcripts of the Timbre pitch audio | 15/18; no wrong WRITTEN or CONTRADICTED (precision 1.0 for both), misses fall to NOT_IN_WRITING or MISSED — [demo/eval_rules_stt.md](demo/eval_rules_stt.md) |
| Mode B on 12 held-out promises (2 new pitches written after the rules) | 2/12; after one post-hoc safety fix, no wrong WRITTEN or CONTRADICTED |
| Mode A with the 4-bit GGUF | not run — no access yet |
| Mode A with BF16 on vLLM | not run — no GPU |
