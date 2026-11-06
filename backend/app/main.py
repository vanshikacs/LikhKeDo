"""FastAPI app, CORS, routers."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .config import get_settings
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
    allow_origins=[o.strip() for o in settings.frontend_origin.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.websocket("/api/cases/{case_id}/listen")
async def listen(ws: WebSocket, case_id: str):
    await proxy(ws, case_id)
