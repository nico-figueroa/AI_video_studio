from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from repositories.production_repository import ProductionRepository
from schemas.stage_generation import (
    AutomaticGenerationApproval, AutomaticGenerationState, GenerationStage,
    RenderMode, StageGenerationRequest, StageGenerationState,
)
from services.stage_generation_service import StageGenerationService

router = APIRouter(prefix="/api/v1/projects/{project_id}")


@router.get("/automatic-generation", response_model=AutomaticGenerationState)
def approval_state(project_id: int, mode: RenderMode = "local_animation",
                   db: Session = Depends(get_db)) -> AutomaticGenerationState:
    return StageGenerationService(ProductionRepository(db)).approval_state(project_id, mode)


@router.post("/automatic-generation", response_model=AutomaticGenerationState)
def approve(project_id: int, payload: AutomaticGenerationApproval,
            db: Session = Depends(get_db)) -> AutomaticGenerationState:
    return StageGenerationService(ProductionRepository(db)).approve(project_id, payload)


@router.get("/generation/{stage}", response_model=StageGenerationState)
def stage_state(project_id: int, stage: GenerationStage, db: Session = Depends(get_db)) -> StageGenerationState:
    return StageGenerationService(ProductionRepository(db)).state(project_id, stage)


def run_stage(job_id: str) -> None:
    with SessionLocal() as db:
        StageGenerationService(ProductionRepository(db)).run(job_id)


@router.post("/generation/{stage}", response_model=StageGenerationState)
def generate_stage(project_id: int, stage: GenerationStage, payload: StageGenerationRequest,
                   tasks: BackgroundTasks, db: Session = Depends(get_db),
                   review_override: Annotated[str, Header(alias="X-Workflow-Override")] = "") -> StageGenerationState:
    state = StageGenerationService(ProductionRepository(db)).start(
        project_id, stage, retry=payload.retry, review_override=review_override,
    )
    if state.job and state.job.status == "queued":
        tasks.add_task(run_stage, state.job.job_id)
    return state
