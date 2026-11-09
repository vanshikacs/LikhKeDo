# Deploying LikhKeDo

Backend: Render (Docker web service). Frontend: Vercel (static Vite build). Evon: optional (Kaggle 4-bit GGUF,
see EVON_FREE.md); the public site works without it by serving the saved cases. Keys go only into the Render
dashboard, never into the repo.

**Status (9 Nov): not deployed yet.** No production URL exists; the URLs below are placeholders. The Docker image
has not been built locally (Docker is not installed on the build machine), so the first Render build is also the
first Docker build.

## 1. Backend on Render

1. Push the repo to GitHub (already at `github.com/vanshikacs/LikhKeDo`).
2. Render dashboard → **New +** → **Blueprint** → connect GitHub → pick `LikhKeDo` → Render reads
   `render.yaml` and proposes the `likhkedo-api` service → **Apply**.
   (Manual alternative: **New + → Web Service** → the repo → Runtime **Docker** → Dockerfile path
   `./backend/Dockerfile` → Docker build context `.` → Health check path `/api/health`.)
3. In the service → **Environment**, set:

   | Key | Value |
   | --- | --- |
   | `GNANI_API_KEY` | from app.gnani.ai |
   | `EVON_BASE_URL` | the tunnel URL ending in `/v1` while Evon runs; leave unset when it is off |
   | `EVON_API_KEY` | the same value as the Kaggle secret `EVON_API_KEY` (or `vllm serve --api-key`) |
   | `EVON_MODEL` | `gnani/gnani-evon-v3.3-30B-A3B` (preset) |
   | `EVON_PROVIDER` | `vllm` (BF16 on a GPU), `llamacpp` (free Kaggle 4-bit GGUF, set `EVON_MODEL=evon`, see EVON_FREE.md) or `none` |
   | `EVON_QUANT` / `EVON_LABEL` | optional: e.g. `IQ4_XS`; label override shown on reports |
   | `FRONTEND_ORIGIN` | your exact Vercel production URL, `https://<your-project>.vercel.app` (comma-separate several) |
   | `DEMO_ONLY` | `true` for the public site (saved cases; live checks answer 503 with a link to them), `false` while Evon is running |
   | `ANALYSES_PER_HOUR` / `RECALLS_PER_HOUR` / `LISTENS_PER_HOUR` | optional, defaults 3 / 20 / 6 per visitor |
   | `ADMIN_SECRET` | `python -c "import secrets;print(secrets.token_urlsafe(24))"` |
   | `DATA_DIR` | `/tmp/likhkedo` (preset) |

4. **Manual Deploy → Deploy latest commit**. Wait for "Live", then open `https://<service>.onrender.com/api/health`.

Notes
- WebSockets (`/api/cases/{id}/listen`) work on Render web services with no extra setting; the app runs
  uvicorn with `--proxy-headers`, and the browser uses `wss://` automatically for an `https` API URL.
- The seeded demo cases (`demo/cache/`) and the sample CIS PDF are copied into the image.
- The free tier sleeps when idle: open the site a minute before recording or presenting.
- Data lives in `/tmp` and is purged after 24 h (and on every redeploy).

## 2. Frontend on Vercel

1. Vercel → **Add New… → Project** → import `LikhKeDo` from GitHub.
2. **Root Directory**: `frontend`. Framework preset: **Vite** (build `npm run build`, output `dist`;
   `frontend/vercel.json` also sets these and the SPA rewrite).
3. **Environment Variables**: `VITE_API_URL` = `https://<service>.onrender.com` (no trailing slash).
4. **Deploy**. Copy the production URL into Render's `FRONTEND_ORIGIN` and redeploy the backend.

## 3. Smoke test (after every deploy)

| # | Check | Expected |
| --- | --- | --- |
| 1 | `GET /api/health` | `{"ok":true, "gnani":"ok", "evon":"ok" or "down", "queue":0, "demo_only":…}` |
| 2 | Site → **See a demo** | Hindi and Tamil only (Marathi is held back); report opens with the badge *Saved from a live check*; summary audio plays; slip opens |
| 3 | Recall: hold the button, say one promise, submit; then type a line in *Or type what was said* | transcript appears (1 Prisma call); typed line is added |
| 4 | Document → sample Bharosa Life → Check | progress "Checking promise i of n", then the report (needs Evon; with `DEMO_ONLY=true` you get the demo message instead) |
| 5 | Listen: tick consent, Start, speak, Stop | captions within 1–2 s of each pause; "guaranteed" lights a chip |
| 6 | Report → **Play summary** | Tarika voice plays (spends Timbre credits once; cached after) |
| 7 | Report → **Likh Ke Do slip** | printable page listing unwritten/contradicted promises |
| 8 | Report → **Delete my data** | "Your data was deleted"; `GET /api/cases/{id}/report` → 404 |
| 9 | `/api/health` again | `queue` is `0` (the Gnani lock was released) |

## 4. When the GPU is off

Set `DEMO_ONLY=true` on Render. `/analyze` then returns 503 with a pointer to the demo case, and the UI
offers **Open the demo case** and the clearly labelled *Rules check — no AI model*. A failed live check never
turns into a result that looks like a live one. Turn it back to `false` when Evon is up again.

## 5. After deploying: verify the real URLs

Open both in a private window: `https://<service>.onrender.com/api/health` and the Vercel URL. Check the saved
cases, audio and slip, and the browser console for CORS or mixed-content errors. Only then call it deployed.
