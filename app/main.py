from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routers import accounts, jobs, posts, sources
from app.config import settings
from app.services.scheduler_service import scheduler_service


@asynccontextmanager
async def lifespan(app: FastAPI):
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
