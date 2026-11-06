# LikhKeDo

"Put it in writing": hears an insurance/bank sales pitch, extracts each spoken promise, and checks it
against the policy's Customer Information Sheet. Synthetic demo data only. Not financial or legal advice.

## Run locally

```
python -m venv backend/.venv
backend/.venv/Scripts/pip install -r backend/requirements.txt   # macOS/Linux: backend/.venv/bin/pip
cd frontend && npm install && cd ..
cp .env.example .env    # then fill in your keys
```

| Task | With make | Without make (Windows) |
| --- | --- | --- |
| Backend dev server | `make dev-backend` | `cd backend; .venv\Scripts\python -m uvicorn app.main:app --reload --port 8000` |
| Frontend dev server | `make dev-frontend` | `cd frontend; npm run dev` |
| Backend tests | `make test` | `cd backend; .venv\Scripts\python -m pytest -q` |

## Measured API behaviour

_To be filled in Phase 1._
