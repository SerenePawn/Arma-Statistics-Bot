from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from .api.router import router as api_router
from .core.config import load_settings
from .core.db import close_pool, init_pool
from .core.state import state
from .core.telegram import close_bot, init_bot

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Arma Stat Counter Web App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    state.settings = load_settings()
    logger.info("Starting Arma Stat Counter web app")
    state.db_pool = await init_pool()
    state.bot = init_bot(state.settings)


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_bot()
    state.bot = None
    await close_pool(state.db_pool)
    state.db_pool = None
    logger.info("Arma Stat Counter web app stopped")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(api_router)
