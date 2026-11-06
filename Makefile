ifeq ($(OS),Windows_NT)
PY := backend/.venv/Scripts/python
else
PY := backend/.venv/bin/python
endif

.PHONY: dev-backend dev-frontend test

dev-backend:
	cd backend && ../$(PY) -m uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && ../$(PY) -m pytest -q
