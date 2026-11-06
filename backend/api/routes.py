import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import STORAGE_DIR, SessionLocal, get_db
from models.models import Character, Job, Project, Scene
from repositories.project_repository import ProjectRepository
from schemas.schemas import (
    CharacterOut,
    CharacterUpdate,
    EstimateComparison,
    JobOut,
    MetricsOut,
    PlanSelected,
    PlanSelection,
    ProjectCreate,
    ProjectCreated,
    ProjectDetail,
    ProjectSummary,
    SceneOut,
    SceneUpdate,
    StatusOut,
    StoryOut,
    StoryUpdate,
    StoryUpdated,
    VideoLink,
    VideoQueued,
    VideoRequest,
)
from services.estimation_service import EstimationService
from services.image_service import PlaceholderImageProvider, public_asset_url
from services.project_service import ProjectService
from services.story_service import StoryService
from services.video_service import VideoService


router = APIRouter(prefix="/api/v1")
image_provider = PlaceholderImageProvider()
logger = logging.getLogger(__name__)
video_composer = VideoService()


def project_service(db: Session) -> ProjectService:
    return ProjectService(ProjectRepository(db))


def project_summary(project: Project) -> dict[str, object]:
    estimate = next(
        (item for item in project.estimates if item.plan_name == project.selected_plan),
        None,
    )
    return {
        "id": project.id,
        "title": project.title,
        "status": project.status,
        "target_minutes": project.target_minutes,
        "selected_plan": project.selected_plan,
        "created_at": project.created_at,
        "estimated_cost": estimate.estimated_cost if estimate else None,
    }


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/projects", response_model=ProjectCreated, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> dict[str, object]:
    project = project_service(db).create(
        prompt=payload.prompt,
        target_minutes=payload.target_minutes,
        max_budget=payload.max_budget,
        max_wait_minutes=payload.max_wait_minutes,
    )
    return {"project_id": project.id, "status": project.status}


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return [project_summary(project) for project in ProjectRepository(db).list_projects()]


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def get_project(project_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    project = project_service(db).get(project_id)
    return {
        **project_summary(project),
        "prompt": project.prompt,
        "max_budget": project.max_budget,
        "max_wait_minutes": project.max_wait_minutes,
        "video_url": public_asset_url(Path(project.video_path)) if project.video_path else None,
    }


@router.post("/projects/{project_id}/analyze", response_model=StatusOut)
def analyze_project(
    project_id: int,
    refresh: bool = False,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    project_service(db).analyze(project_id, refresh=refresh)
    return {"status": "completed"}


@router.get("/projects/{project_id}/estimates", response_model=EstimateComparison)
def get_estimates(project_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    project = project_service(db).get(project_id)
    if not project.estimates:
        raise HTTPException(status_code=409, detail="Analyze the project to create estimates.")
    return EstimationService.as_comparison(project.estimates)


@router.post("/projects/{project_id}/select-plan", response_model=PlanSelected)
def select_plan(
    project_id: int,
    payload: PlanSelection,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    project_service(db).select_plan(project_id, payload.plan)
    return {"selected_plan": payload.plan}


@router.get("/projects/{project_id}/story", response_model=StoryOut)
def get_story(project_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    project = project_service(db).get(project_id)
    if not project.scenes:
        raise HTTPException(status_code=409, detail="Analyze the project to create its story.")
    return {
        "title": project.title,
        "summary": project.story_summary,
        "characters": project.characters,
        "scenes": sorted(project.scenes, key=lambda scene: scene.scene_number),
    }


@router.put("/projects/{project_id}/story", response_model=StoryUpdated)
def update_story(
    project_id: int,
    payload: StoryUpdate,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    repository = ProjectRepository(db)
    repository.begin_write()
    repository.require_no_active_job(project_id)
    project = ProjectService(repository).get(project_id)
    StoryService(repository).update(
        project, payload.title, payload.summary, payload.characters, payload.scenes
    )
    return {"updated": True}


@router.post("/projects/{project_id}/story/regenerate", response_model=StatusOut)
def regenerate_story(project_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    project_service(db).analyze(project_id, refresh=True)
    return {"status": "completed"}


@router.get("/projects/{project_id}/characters", response_model=list[CharacterOut])
def get_characters(project_id: int, db: Session = Depends(get_db)) -> list[Character]:
    return project_service(db).get(project_id).characters


@router.post("/characters/{character_id}/portrait", response_model=StatusOut)
def generate_portrait(character_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    repository = ProjectRepository(db)
    repository.begin_write()
    character = repository.get_character(character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="Character not found.")
    project = project_service(db).get(character.project_id)
    if not project.selected_plan:
        raise HTTPException(status_code=409, detail="Choose a production plan before generating portraits.")
    variation = uuid4().hex
    image = image_provider.generate_character(character, project.id, variation)
    character.image_path = f"{public_asset_url(image)}?v={variation}"
    character.approved = False
    repository.add_asset(project_id=project.id, asset_type="character_image", file_path=str(image))
    repository.save()
    return {"status": "completed"}


@router.put("/characters/{character_id}", response_model=CharacterOut)
def update_character(
    character_id: int,
    payload: CharacterUpdate,
    db: Session = Depends(get_db),
) -> Character:
    character = ProjectRepository(db).get_character(character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="Character not found.")
    character.approved = payload.approved
    db.commit()
    db.refresh(character)
    return character


@router.get("/projects/{project_id}/scenes", response_model=list[SceneOut])
def get_scenes(project_id: int, db: Session = Depends(get_db)) -> list[Scene]:
    project = project_service(db).get(project_id)
    return sorted(project.scenes, key=lambda scene: scene.scene_number)


def generate_scene_image(scene_id: int, db: Session, regenerate: bool = False) -> None:
    repository = ProjectRepository(db)
    repository.begin_write()
    scene = repository.get_scene(scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found.")
    repository.require_no_active_job(scene.project_id)
    project = ProjectService(repository).get(scene.project_id)
    if not project.selected_plan:
        raise HTTPException(status_code=409, detail="Choose a production plan before generating scene images.")
    if scene.image_path and not regenerate:
        return
    variation = uuid4().hex if regenerate else ""
    image = image_provider.generate_scene(scene, project.id, variation)
    scene.image_path = f"{public_asset_url(image)}?v={variation}" if variation else public_asset_url(image)
    scene.status = "generated"
    scene.approved = False
    repository.add_asset(project_id=project.id, asset_type="scene_image", file_path=str(image))
    repository.save()


@router.post("/scenes/{scene_id}/generate", response_model=StatusOut)
def generate_scene(scene_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    generate_scene_image(scene_id, db)
    return {"status": "completed"}


@router.post("/scenes/{scene_id}/regenerate", response_model=StatusOut)
def regenerate_scene(scene_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    generate_scene_image(scene_id, db, regenerate=True)
    return {"status": "completed"}


@router.put("/scenes/{scene_id}", response_model=SceneOut)
def update_scene(
    scene_id: int,
    payload: SceneUpdate,
    db: Session = Depends(get_db),
) -> Scene:
    scene = ProjectRepository(db).get_scene(scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found.")
    scene.approved = payload.approved
    scene.status = "approved" if payload.approved else ("generated" if scene.image_path else "pending")
    db.commit()
    db.refresh(scene)
    return scene


def run_video_job(job_id: str) -> None:
    with SessionLocal() as db:
        repository = ProjectRepository(db)
        job = repository.get_job(job_id)
        if job is None:
            return
        project = project_service(db).get(job.project_id)
        scenes = sorted(project.scenes, key=lambda scene: scene.scene_number)
        try:
            job.status = "running"
            job.progress = 5
            job.current_stage = "Preparing scene artwork"
            job.started_at = datetime.now(timezone.utc)
            db.commit()
            for index, scene in enumerate(scenes):
                if not scene.image_path:
                    image = image_provider.generate_scene(scene, project.id)
                    scene.image_path = public_asset_url(image)
                    scene.status = "generated"
                    repository.add_asset(project_id=project.id, asset_type="scene_image", file_path=str(image))
                job.progress = 10 + round(35 * (index + 1) / max(1, len(scenes)))
                db.commit()

            job.current_stage = "Composing MP4"
            job.progress = 55
            db.commit()
            video = video_composer.compose(project, scenes, project.target_minutes)
            project.video_path = str(video)
            project.status = "completed"
            project.actual_cost = 0
            repository.add_asset(project_id=project.id, asset_type="video", file_path=str(video))
            job.status = "completed"
            job.progress = 100
            job.current_stage = "Export complete"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as error:
            logger.exception("Video generation job %s failed", job_id)
            db.rollback()
            failed_job = repository.get_job(job_id)
            if failed_job is not None:
                failed_job.status = "failed"
                failed_job.current_stage = "Export failed"
                failed_job.error = str(error)[:2000]
                failed_job.completed_at = datetime.now(timezone.utc)
            failed_project = project_service(db).get(job.project_id)
            failed_project.status = "generation_failed"
            db.commit()


@router.post("/projects/{project_id}/video", response_model=VideoQueued, status_code=202)
def start_video(
    project_id: int,
    payload: VideoRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    ProjectRepository(db).begin_write()
    service = project_service(db)
    project = service.get(project_id)
    if project.selected_plan != payload.plan:
        raise HTTPException(status_code=409, detail="Select and approve this plan before generating.")
    service.select_plan(project_id, payload.plan, commit=False)
    if not project.scenes:
        raise HTTPException(status_code=409, detail="Analyze the project before generating a video.")
    active_job = (
        db.query(Job)
        .filter(Job.project_id == project_id, Job.status.in_(["queued", "running"]))
        .first()
    )
    if active_job:
        raise HTTPException(status_code=409, detail="A generation job is already running for this project.")
    job_id = str(uuid4())
    db.add(Job(id=job_id, project_id=project_id))
    project.status = "generating"
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.query(Job).filter(
            Job.project_id == project_id, Job.status.in_(["queued", "running"])
        ).first():
            raise HTTPException(status_code=409, detail="A generation job is already running for this project.")
        raise
    background_tasks.add_task(run_video_job, job_id)
    return {"job_id": job_id, "status": "queued"}


@router.get("/projects/{project_id}/active-job", response_model=JobOut | None)
def get_active_job(project_id: int, db: Session = Depends(get_db)) -> dict[str, object] | None:
    project_service(db).get(project_id)
    job = db.query(Job).filter(
        Job.project_id == project_id, Job.status.in_(["queued", "running"])
    ).first()
    return get_job(job.id, db) if job else None


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    job = ProjectRepository(db).get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Generation job not found.")
    project = project_service(db).get(job.project_id)
    return {
        "job_id": job.id,
        "project_id": job.project_id,
        "status": job.status,
        "progress": job.progress,
        "current_stage": job.current_stage,
        "error": job.error,
        "video_url": public_asset_url(Path(project.video_path)) if project.video_path else None,
    }


@router.get("/projects/{project_id}/video", response_model=VideoLink)
def get_video(project_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    project = project_service(db).get(project_id)
    if not project.video_path or not Path(project.video_path).exists():
        raise HTTPException(status_code=404, detail="This project does not have an exported video yet.")
    return {"url": public_asset_url(Path(project.video_path))}


@router.get("/projects/{project_id}/video/download")
def download_video(project_id: int, db: Session = Depends(get_db)) -> FileResponse:
    project = project_service(db).get(project_id)
    if not project.video_path or not Path(project.video_path).is_file():
        raise HTTPException(status_code=404, detail="This project does not have an exported video yet.")
    return FileResponse(project.video_path, media_type="video/mp4", filename=f"project-{project_id}.mp4")


@router.get("/projects/{project_id}/metrics", response_model=MetricsOut)
def get_metrics(project_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    project = project_service(db).get(project_id)
    estimate = next(
        (item for item in project.estimates if item.plan_name == project.selected_plan),
        None,
    )
    jobs = db.query(Job).filter(Job.project_id == project_id, Job.status == "completed").all()
    actual_time = None
    if jobs:
        latest = max(jobs, key=lambda job: (job.completed_at or job.started_at).timestamp())
        if latest.started_at and latest.completed_at:
            actual_time = max(
                0,
                round((latest.completed_at - latest.started_at).total_seconds() / 60),
            )
    return {
        "estimated_cost": estimate.estimated_cost if estimate else 0,
        "actual_cost": project.actual_cost,
        "estimated_time": estimate.estimated_minutes if estimate else 0,
        "actual_time": actual_time,
        "total_images": sum(1 for scene in project.scenes if scene.image_path),
        "video_length_seconds": project.target_minutes * 60 if project.video_path else None,
    }
