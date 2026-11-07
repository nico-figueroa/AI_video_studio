from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from repositories.production_repository import ProductionRepository
from schemas.animation import AnimationRequest, AnimationReview, AnimationState, AnimationStatus
from services.animation_service import AnimationService

router = APIRouter(prefix="/api/v1/projects/{project_id}/scenes/{scene_id}/animation")


@router.get("", response_model=AnimationState)
def state(project_id: int, scene_id: int, db: Session = Depends(get_db)) -> AnimationState:
    return AnimationService(ProductionRepository(db)).state(project_id, scene_id)


def run_animation(job_id: str) -> None:
    with SessionLocal() as db:
        AnimationService(ProductionRepository(db)).run(job_id)


@router.post("", response_model=AnimationStatus, status_code=202)
def start(project_id: int, scene_id: int, payload: AnimationRequest,
          background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> AnimationStatus:
    result = AnimationService(ProductionRepository(db)).start(project_id, scene_id, payload)
    background_tasks.add_task(run_animation, result.job_id)
    return result


@router.put("/approval", response_model=AnimationStatus)
def review(project_id: int, scene_id: int, payload: AnimationReview,
           db: Session = Depends(get_db)) -> AnimationStatus:
    return AnimationService(ProductionRepository(db)).review(project_id, scene_id, payload)
