import logging
from datetime import datetime, timezone
import os
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
    AISettingsOut,
    AISettingsUpdate,
    CharacterOut,
    CharacterUpdate,
    EstimateComparison,
    GenerationEstimatesOut,
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
from services.ai.configuration import create_ai_provider, get_ai_configuration
from services.ai.estimation_service import AIEstimationService, GenerationEstimate
from services.image_service import PlaceholderImageProvider, public_asset_url
from services.project_service import ProjectService
from services.story_service import StoryService
from services.video_service import VideoService


router = APIRouter(prefix="/api/v1")
legacy_video_image_provider = PlaceholderImageProvider()
image_provider = legacy_video_image_provider
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


def generation_estimates(
    project: Project, db: Session
) -> dict[str, GenerationEstimate]:
    configuration = get_ai_configuration(db)
    estimator = AIEstimationService()
    scene_count = len(project.scenes) or estimator.scene_count_for(project.target_minutes)
    character_count = len(project.characters) or 3
    estimates = estimator.estimate_all(configuration, character_count, scene_count)
    return {estimate.operation: estimate for estimate in estimates}


def estimate_project_operation(
    project: Project, db: Session, operation: str
) -> GenerationEstimate:
    return generation_estimates(project, db)[operation]


def reserve_estimated_cost(
    project: Project, db: Session, estimate: GenerationEstimate
) -> None:
    cost = estimate.estimated_cost
    if project.estimated_spend + cost > project.max_budget:
        raise HTTPException(
            status_code=422,
            detail=(
                f"This generation is estimated at ${cost:.4f}, which would exceed the "
                f"remaining project budget of ${max(0, project.max_budget - project.estimated_spend):.4f}."
            ),
        )
    project.estimated_spend = round(project.estimated_spend + cost, 4)
    db.commit()


def refund_estimated_cost(project_id: int, db: Session, cost: float) -> None:
    repository = ProjectRepository(db)
    if not db.in_transaction():
        repository.begin_write()
        repository.lock_project(project_id)
    project = project_service(db).get(project_id)
    project.estimated_spend = round(max(0, project.estimated_spend - cost), 4)
    repository.save()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/settings/ai", response_model=AISettingsOut)
def get_ai_settings(db: Session = Depends(get_db)) -> dict[str, object]:
    configuration = get_ai_configuration(db)
    db.commit()
    return {
        "provider": configuration.provider,
        "model": configuration.model,
        "image_model": configuration.image_model,
        "default_budget": configuration.default_budget,
        "default_wait_minutes": configuration.default_wait_minutes,
        "api_key_configured": bool(os.getenv("OPENAI_API_KEY")),
    }


@router.put("/settings/ai", response_model=AISettingsOut)
def update_ai_settings(
    payload: AISettingsUpdate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    configuration = get_ai_configuration(db)
    configuration.provider = payload.provider
    configuration.model = payload.model.strip()
    configuration.image_model = payload.image_model.strip()
    configuration.default_budget = payload.default_budget
    configuration.default_wait_minutes = payload.default_wait_minutes
    configuration.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(configuration)
    return get_ai_settings(db)


@router.post("/projects", response_model=ProjectCreated, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> dict[str, object]:
    configuration = get_ai_configuration(db)
    values = payload.model_dump()
    if "max_budget" not in payload.model_fields_set:
        values["max_budget"] = configuration.default_budget
    if "max_wait_minutes" not in payload.model_fields_set:
        values["max_wait_minutes"] = configuration.default_wait_minutes
    project = project_service(db).create(
        **values,
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
        "estimated_spend": project.estimated_spend,
        "video_url": public_asset_url(Path(project.video_path)) if project.video_path else None,
    }


@router.get(
    "/projects/{project_id}/generation-estimates",
    response_model=GenerationEstimatesOut,
)
def get_generation_estimates(
    project_id: int, db: Session = Depends(get_db)
) -> dict[str, object]:
    project = project_service(db).get(project_id)
    return generation_estimates(project, db)


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
        "genre": project.genre,
        "target_audience": project.target_audience,
        "three_act_structure": project.three_act_structure,
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
    repository.lock_project(project_id)
    repository.require_no_active_job(project_id)
    project = ProjectService(repository).get(project_id)
    StoryService(repository).update(
        project,
        payload.title,
        payload.summary,
        payload.genre,
        payload.target_audience,
        payload.three_act_structure,
        payload.characters,
        payload.scenes,
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
    repository.lock_project(project.id)
    repository.require_no_active_job(project.id)
    project = project_service(db).get(project.id)
    character = repository.get_character(character_id)
    if character is None or character.project_id != project.id:
        raise HTTPException(status_code=404, detail="Character not found.")
    initial_image_path = character.image_path
    provider = create_ai_provider(get_ai_configuration(db))
    estimate = estimate_project_operation(project, db, "character_portrait")
    reserve_estimated_cost(project, db, estimate)
    repository.begin_write()
    repository.lock_project(project.id)
    try:
        repository.require_no_active_job(project.id)
    except HTTPException:
        refund_estimated_cost(project.id, db, estimate.estimated_cost)
        raise
    project = project_service(db).get(project.id)
    character = repository.get_character(character_id)
    if character is None or character.project_id != project.id:
        refund_estimated_cost(project.id, db, estimate.estimated_cost)
        raise HTTPException(status_code=404, detail="Character not found.")
    if character.image_path and character.image_path != initial_image_path:
        refund_estimated_cost(project.id, db, estimate.estimated_cost)
        return {"status": "completed"}
    variation = uuid4().hex
    image = provider.generate_character_portrait(
        character.portrait_prompt or character.description,
        STORAGE_DIR / "projects" / str(project.id) / f"character-{character.id}.png",
    )
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
    repository.lock_project(project.id)
    repository.require_no_active_job(project.id)
    project = ProjectService(repository).get(project.id)
    scene = repository.get_scene(scene_id)
    if scene is None or scene.project_id != project.id:
        raise HTTPException(status_code=404, detail="Scene not found.")
    if scene.image_path and not regenerate:
        return
    initial_image_path = scene.image_path
    provider = create_ai_provider(get_ai_configuration(db))
    estimate = estimate_project_operation(project, db, "scene_image")
    reserve_estimated_cost(project, db, estimate)
    repository.begin_write()
    repository.lock_project(project.id)
    try:
        repository.require_no_active_job(project.id)
    except HTTPException:
        refund_estimated_cost(project.id, db, estimate.estimated_cost)
        raise
    project = ProjectService(repository).get(project.id)
    scene = repository.get_scene(scene_id)
    if scene is None or scene.project_id != project.id:
        refund_estimated_cost(project.id, db, estimate.estimated_cost)
        raise HTTPException(status_code=404, detail="Scene not found.")
    if not regenerate and scene.image_path:
        refund_estimated_cost(project.id, db, estimate.estimated_cost)
        return
    if regenerate and scene.image_path and scene.image_path != initial_image_path:
        refund_estimated_cost(project.id, db, estimate.estimated_cost)
        return
    variation = uuid4().hex
    image = provider.generate_scene_image(
        scene.image_prompt or scene.visual_description or scene.description,
        STORAGE_DIR / "projects" / str(project.id) / f"scene-{scene.id}.png",
    )
    scene.image_path = f"{public_asset_url(image)}?v={variation}"
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
                    image = legacy_video_image_provider.generate_scene(scene, project.id)
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
    repository = ProjectRepository(db)
    repository.begin_write()
    repository.lock_project(project_id)
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
        "estimated_ai_spend": project.estimated_spend,
        "actual_provider_cost": None,
        "estimated_time": estimate.estimated_minutes if estimate else 0,
        "actual_time": actual_time,
        "total_images": sum(1 for scene in project.scenes if scene.image_path),
        "video_length_seconds": project.target_minutes * 60 if project.video_path else None,
    }
