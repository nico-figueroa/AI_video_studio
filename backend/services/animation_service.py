import logging
import json
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from models.models import AnimationJob, Scene
from repositories.production_repository import ProductionRepository
from schemas.animation import AnimationRequest, AnimationReview, AnimationState, AnimationStatus
from schemas.production import ProductionEstimate
from services.ai.providers.local_svd import LocalSVDProvider, MODEL_REVISION
from services.image_service import public_asset_url
from services.project_service import ProjectService
from services.scene_motion_planner import SceneMotionPlanner
from services.timeline_service import fingerprint, local_media
import services.image_service as media

logger = logging.getLogger(__name__)


def animation_source(project, scene: Scene) -> str:
    from services.story_memory_service import StoryMemoryService
    return fingerprint([
        StoryMemoryService().context(project, scene), scene.image_path,
        SceneMotionPlanner().get(project, scene).model_dump(), MODEL_REVISION,
    ])


def selected_animation(db, scene: Scene) -> AnimationJob | None:
    job = db.scalar(select(AnimationJob).where(
        AnimationJob.scene_id == scene.id, AnimationJob.approved.is_(True),
        AnimationJob.status == "completed",
    ).order_by(AnimationJob.created_at.desc(), AnimationJob.id.desc()).limit(1))
    return job


def animation_problem(project, scene: Scene, job: AnimationJob) -> str | None:
    if job.source_hash != animation_source(project, scene):
        return "Approved animation is stale. Generate/review a replacement or deselect it."
    if not job.clip_path or not Path(job.clip_path).is_file():
        return "Approved animation file is missing. Restore or deselect it."
    return None


class AnimationService:
    def __init__(self, repository: ProductionRepository):
        self.repository = repository

    def scene(self, project_id: int, scene_id: int):
        project = ProjectService(self.repository).get(project_id)
        scene = next((item for item in project.scenes if item.id == scene_id), None)
        if scene is None:
            raise HTTPException(status_code=404, detail="Project scene not found.")
        return project, scene

    def state(self, project_id: int, scene_id: int) -> AnimationState:
        project, scene = self.scene(project_id, scene_id)
        quote = LocalSVDProvider().estimate_animation_cost()
        job = self.repository.db.scalar(select(AnimationJob).where(
            AnimationJob.scene_id == scene_id,
        ).order_by(AnimationJob.created_at.desc(), AnimationJob.id.desc()).limit(1))
        current_source = animation_source(project, scene)
        return AnimationState(
            estimate=ProductionEstimate(
                estimate_id=fingerprint(["animation", current_source, quote]),
                estimated_cost=0, estimated_runtime_seconds=quote["runtime_seconds"],
                estimated_storage_mb=quote["storage_mb"], estimated_audio_seconds=0,
                estimated_video_seconds=2, estimated_api_calls=0,
                model_usage=quote["model"], notes=quote["limitations"],
            ),
            job=self.status(job, current_source) if job else None,
        )

    @staticmethod
    def status(job: AnimationJob, current_source: str) -> AnimationStatus:
        progress = job.progress
        if job.status == "running":
            progress_file = (media.STORAGE_DIR / "projects" / str(job.project_id) /
                             f"animation-{job.id}.progress.json")
            if progress_file.is_file():
                progress = max(progress, min(95, int(json.loads(progress_file.read_text(encoding="utf-8"))["progress"])))
        return AnimationStatus(
            job_id=job.id, scene_id=job.scene_id, status=job.status, progress=progress,
            error=job.error, approved=job.approved, stale=job.source_hash != current_source,
            clip_url=public_asset_url(Path(job.clip_path)) if job.clip_path else None,
            metadata=job.result_metadata,
        )

    def start(self, project_id: int, scene_id: int, request: AnimationRequest,
              *, parent_job_id: str | None = None) -> AnimationStatus:
        self.repository.begin_write()
        self.repository.lock_project(project_id)
        self.repository.require_no_active_job(project_id, excluding_job_id=parent_job_id)
        project, scene = self.scene(project_id, scene_id)
        if project.status == "planning" or not scene.approved or not scene.image_path:
            raise HTTPException(status_code=409, detail="Finish planning and approve this scene image first.")
        image = local_media(project_id, scene.image_path)
        state = self.state(project_id, scene_id)
        if state.estimate.estimate_id != request.estimate_id:
            raise HTTPException(status_code=409, detail="Animation estimate changed. Review it again.")
        if state.estimate.estimated_runtime_seconds > project.max_wait_minutes * 60:
            raise HTTPException(status_code=422, detail="Animation estimate exceeds the project wait limit.")
        LocalSVDProvider().check_ready()
        job = AnimationJob(
            id=str(uuid4()), project_id=project_id, scene_id=scene_id,
            source_hash=animation_source(project, scene),
            snapshot={"image": str(image), "seed": request.seed,
                      "motion_plan": SceneMotionPlanner().get(project, scene).model_dump()},
        )
        self.repository.db.add(job)
        project.status = "animating"
        try:
            self.repository.save()
        except IntegrityError as error:
            self.repository.db.rollback()
            raise HTTPException(status_code=409, detail="The local GPU is already processing an animation.") from error
        return self.status(job, job.source_hash)

    def run(self, job_id: str) -> None:
        job = self.repository.db.scalar(select(AnimationJob).where(
            AnimationJob.id == job_id,
        ).with_for_update())
        if job is None or job.status != "queued":
            raise RuntimeError("Animation job is missing or is no longer queued.")
        job.status, job.progress = "running", 5
        self.repository.save()
        output = media.STORAGE_DIR / "projects" / str(job.project_id) / f"animation-{job.id}.mp4"
        try:
            metadata = LocalSVDProvider().generate_scene_animation(
                Path(job.snapshot["image"]), output, seed=job.snapshot["seed"],
            )
            from services.video_composer_service import VideoComposerService
            VideoComposerService().validate_visual(output)
            job.clip_path = str(output)
            job.result_metadata = metadata
            job.status, job.progress = "completed", 100
            project = ProjectService(self.repository).get(job.project_id)
            project.status = "animation_complete"
            self.repository.save()
        except Exception as error:
            self.repository.db.rollback()
            logger.exception("Local animation job %s failed", job_id)
            job = self.repository.db.get(AnimationJob, job_id)
            if job is None:
                raise RuntimeError(f"Animation job {job_id} disappeared during execution.") from error
            job.status, job.error = "failed", str(error)[:2000]
            project = ProjectService(self.repository).get(job.project_id)
            project.status = "animation_failed"
            self.repository.save()

    def review(self, project_id: int, scene_id: int, request: AnimationReview) -> AnimationStatus:
        self.repository.begin_write()
        self.repository.lock_project(project_id)
        self.repository.require_no_active_job(project_id)
        project, scene = self.scene(project_id, scene_id)
        job = self.repository.db.get(AnimationJob, request.job_id)
        if job is None or job.project_id != project_id or job.scene_id != scene_id:
            raise HTTPException(status_code=404, detail="Animation job not found.")
        source = animation_source(project, scene)
        if request.approved and (job.status != "completed" or not job.clip_path or not Path(job.clip_path).is_file()):
            raise HTTPException(status_code=409, detail="Generate and preview a complete animation first.")
        if request.approved and (job.source_hash != source or not scene.approved):
            raise HTTPException(status_code=409, detail="Animation is stale or scene image is unapproved.")
        for previous in self.repository.db.scalars(select(AnimationJob).where(
            AnimationJob.scene_id == scene_id, AnimationJob.approved.is_(True),
        )):
            previous.approved = False
        job.approved = request.approved
        self.repository.save()
        return self.status(job, source)
