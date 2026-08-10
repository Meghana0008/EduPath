from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.jobs.scheduler import start_scheduler
from app.services.seed import seed_database
from app.utils.schema_migrate import ensure_schema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("edupath")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    # Clear settings cache so .env DEMO_MODE changes apply on boot
    get_settings.cache_clear()
    db = SessionLocal()
    try:
        result = seed_database(db)
        logger.info("Seed complete: %s", result)
    finally:
        db.close()
    try:
        start_scheduler()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Scheduler not started: %s", exc)
    yield


settings = get_settings()
app = FastAPI(title="EduPath AI", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins + ["http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong. Please try again."})


@app.get("/health")
def health():
    return {"status": "ok", "demo_mode": settings.demo_mode}


app.include_router(api_router)
