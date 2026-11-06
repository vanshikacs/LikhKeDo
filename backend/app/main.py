"""FastAPI app, CORS, routers."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings

settings = get_settings()

app = FastAPI(title="LikhKeDo")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}
