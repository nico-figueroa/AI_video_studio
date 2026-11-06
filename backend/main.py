from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api.routes import router
from sqlalchemy import update
from sqlalchemy.orm import Session

from database import STORAGE_DIR, engine, migrate_legacy_storage, run_migrations
from models.models import Job, Project
from services.ai.providers.base import AIProviderConfigurationError, AIProviderError


@asynccontextmanager
async def lifespan(_: FastAPI):
    migrate_legacy_storage()
    (STORAGE_DIR / "projects").mkdir(parents=True, exist_ok=True)
    run_migrations(engine)
    with Session(engine) as db:
        active_projects = db.query(Job.project_id).filter(Job.status.in_(["queued", "running"]))
        db.execute(update(Project).where(Project.id.in_(active_projects)).values(status="generation_failed"))
        db.execute(
            update(Job).where(Job.status.in_(["queued", "running"])).values(
                status="failed", current_stage="Export interrupted",
                error="The backend stopped during export. Please retry.",
                completed_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
    yield


app = FastAPI(
    title="AI Video Studio API",
    description="Local-first story planning, transparent estimates, and slideshow video export.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(AIProviderError)
async def handle_ai_provider_error(_: Request, error: AIProviderError) -> JSONResponse:
    status_code = 503 if isinstance(error, AIProviderConfigurationError) else 502
    return JSONResponse(status_code=status_code, content={"detail": str(error)})


frontend_origins = [
    origin.strip() for origin in os.getenv(
        "STUDIO_FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",") if origin.strip()
]
trusted_origins = set(frontend_origins) | {"http://localhost:8000", "http://127.0.0.1:8000"}
app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def validate_mutation_origin(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if (origin is not None and origin not in trusted_origins) or (
            origin is None and request.headers.get("sec-fetch-site") == "cross-site"
        ):
            return JSONResponse(status_code=403, content={"detail": "Request origin is not allowed."})
    return await call_next(request)


app.include_router(router)
app.mount("/storage/projects", StaticFiles(directory=STORAGE_DIR / "projects", check_dir=False), name="storage")


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "AI Video Studio", "docs": "/docs", "status": "ok"}
