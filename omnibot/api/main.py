from contextlib import asynccontextmanager
from logging import getLogger
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from omnibot.api.routes import router
from omnibot.config import get_settings
from omnibot.db.session import engine, init_db
from omnibot.logging_config import configure_logging

configure_logging()
logger = getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.is_production and settings.session_secret == "development-only-change-me":
        raise RuntimeError("SESSION_SECRET must be changed in production")
    await init_db()
    logger.info("OmniBot API started")
    yield
    await engine.dispose()


app = FastAPI(title="OmniBot API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    https_only=settings.is_production,
    same_site="lax",
    session_cookie="omnibot_session",
    max_age=60 * 60 * 8,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type"],
)
app.include_router(router)

frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="dashboard")
