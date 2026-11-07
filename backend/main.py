from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api.routes import router
from api.production_routes import router as production_router
from api.quality_routes import router as quality_router
from api.input_routes import router as input_router
from api.animation_routes import router as animation_router
from api.stage_generation_routes import router as stage_generation_router
from sqlalchemy import update
from sqlalchemy.orm import Session

from database import STORAGE_DIR, engine, migrate_legacy_storage, run_migrations
from models.models import AnimationJob, Job, Project, RenderJob
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
                status="failed", current_stage="Generation interrupted",
                error="The backend stopped during generation. Review completed assets and explicitly retry missing ones.",
                completed_at=datetime.now(timezone.utc),
            )
        )
        db.execute(
            update(Project).where(Project.status == "planning").values(status="analysis_failed")
        )
        render_projects = db.query(RenderJob.project_id).filter(RenderJob.status.in_(["queued", "running"]))
        db.execute(update(Project).where(Project.id.in_(render_projects)).values(status="render_failed"))
        db.execute(
            update(RenderJob).where(RenderJob.status.in_(["queued", "running"])).values(
                status="failed", current_stage="Render interrupted",
                error="The backend stopped. Approve Resume to reuse completed scene checkpoints.",
                completed_at=datetime.now(timezone.utc),
            )
        )
        db.execute(
            update(Project).where(Project.status.in_(["narrating", "generating_audio"]))
            .values(status="narration_failed")
        )
        db.execute(update(Project).where(Project.status == "transcribing").values(status="transcription_failed"))
        db.execute(update(AnimationJob).where(AnimationJob.status.in_(["queued", "running"])).values(
            status="failed", error="Local animation was interrupted. Review the estimate and explicitly retry.",
        ))
        db.execute(update(Project).where(Project.status == "animating").values(status="animation_failed"))
        db.commit()
    yield


app = FastAPI(
    title="AI Video Studio API",
    description="AI story planning, narrated timelines, approved rendering, and downloadable MP4 production.",
    version="0.3.0",
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
app.include_router(production_router)
app.include_router(quality_router)
app.include_router(input_router)
app.include_router(animation_router)
app.include_router(stage_generation_router)
app.mount("/storage/projects", StaticFiles(directory=STORAGE_DIR / "projects", check_dir=False), name="storage")


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "AI Video Studio", "docs": "/docs", "status": "ok"}
