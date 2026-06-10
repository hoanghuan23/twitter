from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routers import accounts, jobs, posts, sources
from app.config import settings
from app.database import Base, engine
from app.database_migrations import ensure_runtime_schema
import app.models  # noqa: F401
from app.services.scheduler_service import scheduler_service


def configure_logging() -> None:
    app_logger = logging.getLogger("app")
    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    if uvicorn_error_logger.handlers:
        app_logger.handlers = uvicorn_error_logger.handlers
        app_logger.propagate = True
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s:%(name)s:%(message)s",
        )
    app_logger.setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    Base.metadata.create_all(bind=engine)  # tạo tất cả bảng khi startup
    ensure_runtime_schema(engine)
    if settings.scheduler_enabled:
        scheduler_service.start()
    yield
    if settings.scheduler_enabled:
        await scheduler_service.stop()


app = FastAPI(
    title="Twitter Crawler MVP",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(accounts.router)
app.include_router(sources.router)
app.include_router(posts.router)
app.include_router(jobs.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
