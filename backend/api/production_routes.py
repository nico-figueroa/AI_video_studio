from typing import Annotated
from fastapi import APIRouter, BackgroundTasks, Depends, Header
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse

from database import SessionLocal, get_db
from repositories.production_repository import ProductionRepository
from schemas.production import (
    NarrationOut, NarrationRequest, ProductionApproval, ProductionEstimate,
    RenderRequest, RenderStatus, TimelineOut, TimelineUpdate,
)
from services.narration_service import NarrationService
from services.project_service import ProjectService
from services.render_service import RenderService
from services.timeline_service import TimelineService
from schemas.stage_generation import RenderMode

router = APIRouter(prefix="/api/v1/projects/{project_id}")


@router.get("/video/audio")
def playback_audio(project_id: int, render_job_id: str, db: Session = Depends(get_db)) -> FileResponse:
    path = RenderService(ProductionRepository(db)).playback_audio(project_id, render_job_id)
    db.rollback()
    return FileResponse(path, media_type="audio/wav")


@router.get("/narration", response_model=NarrationOut)
def get_narration(project_id: int, db: Session = Depends(get_db)) -> NarrationOut:
    return NarrationService(ProductionRepository(db)).get(project_id)


@router.post("/narration", response_model=NarrationOut)
def generate_narration(project_id: int, payload: NarrationRequest, db: Session = Depends(get_db),
                       review_override: Annotated[str, Header(alias="X-Workflow-Override")] = "") -> NarrationOut:
    return NarrationService(ProductionRepository(db)).generate(project_id, payload, review_override)


@router.post("/narration/audio", response_model=NarrationOut)
def generate_audio(project_id: int, payload: ProductionApproval, db: Session = Depends(get_db),
                   review_override: Annotated[str, Header(alias="X-Workflow-Override")] = "") -> NarrationOut:
    return NarrationService(ProductionRepository(db)).generate_audio(project_id, payload, review_override)


@router.get("/timeline", response_model=TimelineOut)
def get_timeline(project_id: int, db: Session = Depends(get_db)) -> TimelineOut:
    return TimelineService(ProductionRepository(db)).get(project_id)


@router.put("/timeline", response_model=TimelineOut)
def update_timeline(project_id: int, payload: TimelineUpdate, db: Session = Depends(get_db)) -> TimelineOut:
    return TimelineService(ProductionRepository(db)).update(project_id, payload)


@router.get("/render/estimate", response_model=ProductionEstimate)
def render_estimate(project_id: int, mode: RenderMode = "local_animation", db: Session = Depends(get_db)) -> ProductionEstimate:
    return RenderService(ProductionRepository(db)).estimate(project_id, mode)


def run_render_job(job_id: str) -> None:
    with SessionLocal() as db:
        RenderService(ProductionRepository(db)).run(job_id)


@router.post("/render", response_model=RenderStatus, status_code=202)
def start_render(
    project_id: int, payload: RenderRequest, background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    review_override: Annotated[str, Header(alias="X-Workflow-Override")] = "",
) -> RenderStatus:
    result = RenderService(ProductionRepository(db)).start(project_id, payload, review_override)
    background_tasks.add_task(run_render_job, result.job_id)
    return result


@router.get("/render/status", response_model=RenderStatus | None)
def render_status(project_id: int, db: Session = Depends(get_db)) -> RenderStatus | None:
    repository = ProductionRepository(db)
    # A new project has no render yet; missing projects still return 404.
    ProjectService(repository).get(project_id)
    if repository.latest_job(project_id) is None:
        return None
    return RenderService(repository).status(project_id)
