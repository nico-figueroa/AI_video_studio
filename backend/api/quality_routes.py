from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from repositories.production_repository import ProductionRepository
from schemas.quality import MotionUpdate, QualityReport, ReviewRequest
from services.project_service import ProjectService
from services.quality_assessment_service import QualityAssessmentService
from services.timeline_service import TimelineService
from services.workflow_service import story_revision

router = APIRouter(prefix="/api/v1/projects/{project_id}")


@router.get("/film-plan")
def film_plan(project_id: int, db: Session = Depends(get_db)) -> dict:
    from services.scene_continuity_service import SceneContinuityService
    return SceneContinuityService().film_plan(ProjectService(ProductionRepository(db)).get(project_id))

@router.get("/quality", response_model=QualityReport)
def quality(project_id: int, db: Session = Depends(get_db)) -> QualityReport:
    return QualityAssessmentService().assess(ProjectService(ProductionRepository(db)).get(project_id))


@router.post("/story/approval", response_model=QualityReport)
def approve_story(project_id: int, payload: ReviewRequest, db: Session = Depends(get_db)) -> QualityReport:
    repository = ProductionRepository(db)
    repository.begin_write()
    repository.lock_project(project_id)
    repository.require_no_active_job(project_id)
    project = ProjectService(repository).get(project_id)
    if project.status=="planning":
        raise HTTPException(status_code=409,detail="Wait for planning to finish before reviewing content.")
    if not project.story_summary or not project.scenes:
        raise HTTPException(status_code=409, detail="Generate or import a story and scenes first.")
    if payload.revision != story_revision(project):
        raise HTTPException(status_code=409, detail="Story changed. Review the current content before approving.")
    project.story_approved = payload.approved
    repository.save()
    return QualityAssessmentService().assess(project)


@router.put("/scenes/{scene_id}/motion", response_model=QualityReport)
def update_motion(project_id: int, scene_id: int, payload: MotionUpdate, db: Session = Depends(get_db)) -> QualityReport:
    repository = ProductionRepository(db)
    repository.begin_write()
    repository.lock_project(project_id)
    repository.require_no_active_job(project_id)
    project = ProjectService(repository).get(project_id)
    scene = next((item for item in project.scenes if item.id == scene_id), None)
    if scene is None:
        raise HTTPException(status_code=404, detail="Project scene not found.")
    if payload.revision != TimelineService(repository).get(project_id).revision:
        raise HTTPException(status_code=409, detail="Timeline changed. Reload before editing motion.")
    scene.motion_plan = payload.plan.model_dump()
    repository.save()
    return QualityAssessmentService().assess(project)
