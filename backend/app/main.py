"""FastAPI app, CORS, routers."""
import asyncio
import hmac
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .config import get_settings
from .routes import cases, demo, health
from .stream_proxy import proxy

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.engine()
    task = asyncio.create_task(db.purge_loop())
    yield
    task.cancel()


app = FastAPI(title="LikhKeDo", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    # browsers send the origin without a trailing slash; tolerate "https://x.vercel.app/" in the setting
    allow_origins=[o.strip().rstrip("/") for o in settings.frontend_origin.split(",") if o.strip()],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
    expose_headers=["X-Timbre-Model", "X-Cached"],
)
app.include_router(health.router)
app.include_router(cases.router)
app.include_router(demo.router)


@app.websocket("/api/cases/{case_id}/listen")
async def listen(ws: WebSocket, case_id: str):
    await proxy(ws, case_id)


@app.post("/api/admin/purge")
def admin_purge(x_admin_secret: str = Header(default="")) -> dict:
    secret = settings.admin_secret.get_secret_value() if settings.admin_secret else ""
    if not secret or not hmac.compare_digest(x_admin_secret, secret):
        raise HTTPException(403, "Forbidden.")
    return {"purged": db.purge_expired()}
