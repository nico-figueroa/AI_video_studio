from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import router
from sqlalchemy import update
from sqlalchemy.orm import Session

from database import Base, STORAGE_DIR, engine, migrate_legacy_storage
from models.models import Job, Project


@asynccontextmanager
async def lifespan(_: FastAPI):
    migrate_legacy_storage()
    (STORAGE_DIR / "projects").mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
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
    next(index for index in Job.__table__.indexes if index.name == "uq_jobs_active_project").create(
        bind=engine, checkfirst=True
    )
    yield


app = FastAPI(
    title="AI Video Studio API",
    description="Local-first story planning, transparent estimates, and slideshow video export.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.mount("/storage/projects", StaticFiles(directory=STORAGE_DIR / "projects", check_dir=False), name="storage")


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "AI Video Studio", "docs": "/docs", "status": "ok"}
