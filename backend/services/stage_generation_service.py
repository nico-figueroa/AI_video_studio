import logging
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from models.models import AnimationJob, Job, Project, utc_now
from repositories.production_repository import ProductionRepository
from schemas.animation import AnimationRequest
from schemas.production import ProductionEstimate
from schemas.schemas import JobOut
from schemas.stage_generation import (
    AutomaticGenerationApproval, AutomaticGenerationState, GenerationStage,
    RenderMode, StageGenerationState,
)
from services.ai.configuration import create_ai_provider, get_ai_configuration
from services.ai.estimation_service import AIEstimationService
from services.ai.providers.local_svd import LocalSVDProvider
from services.animation_service import AnimationService, animation_source
from services.image_asset_service import ImageAssetService
from services.project_service import ProjectService
from services.timeline_service import fingerprint, local_media
from services.workflow_service import WorkflowService

logger = logging.getLogger(__name__)


class StageGenerationService:
    def __init__(self, repository: ProductionRepository):
        self.repository = repository

    def approval_state(self, project_id: int, mode: RenderMode = "local_animation") -> AutomaticGenerationState:
        project = ProjectService(self.repository).get(project_id)
        configuration = get_ai_configuration(self.repository.db)
        # Before planning, consent covers the bounded schema maximum, never an unknown unlimited count.
        characters = len(project.characters) or 6
        scenes = len(project.scenes) if project.scenes else 12
        image_quote = AIEstimationService().estimate(
            "all_images", configuration, character_count=characters, scene_count=scenes,
        )
        animation_quote = LocalSVDProvider().estimate_animation_cost()
        animation_seconds = scenes * animation_quote["runtime_seconds"] if mode == "local_animation" else 0
        estimate_id = fingerprint([
            project.prompt, project.target_seconds, configuration.provider, configuration.image_model,
            image_quote.estimated_cost, characters, scenes, animation_quote, mode,
        ])
        approval = project.generation_approval
        valid = bool(
            approval and approval.get("prompt_hash") == fingerprint([project.prompt, project.target_seconds])
            and approval.get("image_model") == configuration.image_model
            and approval.get("provider") == configuration.provider
            and approval.get("unit_image_cost") == AIEstimationService().image_usd_per_image
            and approval.get("animation_quote") == animation_quote
            and approval.get("max_characters", 0) >= len(project.characters)
            and approval.get("max_scenes", 0) >= len(project.scenes)
            and approval.get("render_mode") == mode
        )
        return AutomaticGenerationState(
            approved=valid, render_mode=mode, characters=characters, scenes=scenes,
            max_animation_seconds=animation_seconds,
            estimate=ProductionEstimate(
                estimate_id=estimate_id, estimated_cost=image_quote.estimated_cost,
                estimated_runtime_seconds=image_quote.estimated_minutes * 60 + animation_seconds,
                estimated_storage_mb=characters * 10 + scenes * 10 + (
                    scenes * animation_quote["storage_mb"] if mode == "local_animation" else 0
                ),
                estimated_audio_seconds=0, estimated_video_seconds=project.target_seconds,
                estimated_api_calls=image_quote.estimated_api_calls,
                model_usage=f"{configuration.image_model}; " + (
                    animation_quote["model"] if mode == "local_animation" else "explicit still-image camera effects"
                ),
                notes=(
                    f"Upper estimate for {characters} portraits and {scenes} scene images. Missing assets only. "
                    "Entering Characters/Scenes starts its approved batch. Entering Render starts the local GPU "
                    "batch when selected. Existing supplied/generated assets are reused. Narration, speech, "
                    "regeneration and final export need separate approval. Local SVD creates only 2 seconds of "
                    "motion per scene, then holds the final frame; no text-directed gestures or guaranteed identity. "
                    "Non-commercial only, $0 GPU provider fee excluding electricity. Wait limit applies per GPU clip."
                ),
            ),
        )

    def approve(self, project_id: int, request: AutomaticGenerationApproval) -> AutomaticGenerationState:
        self.repository.begin_write()
        self.repository.lock_project(project_id)
        self.repository.require_no_active_job(project_id)
        project = ProjectService(self.repository).get(project_id)
        state = self.approval_state(project_id, request.render_mode)
        if request.estimate_id != state.estimate.estimate_id:
            raise HTTPException(status_code=409, detail="Automatic generation estimate changed. Review it again.")
        configuration = get_ai_configuration(self.repository.db)
        project.generation_approval = {
            "prompt_hash": fingerprint([project.prompt, project.target_seconds]),
            "provider": configuration.provider, "image_model": configuration.image_model,
            "unit_image_cost": AIEstimationService().image_usd_per_image,
            "max_characters": state.characters, "max_scenes": state.scenes,
            "animation_quote": LocalSVDProvider().estimate_animation_cost(),
            "render_mode": request.render_mode,
        }
        self.repository.save()
        return self.approval_state(project_id, request.render_mode)

    def missing(self, project: Project, stage: GenerationStage) -> list[int]:
        if stage == "animations":
            result = []
            for scene in sorted(project.scenes, key=lambda item: item.scene_number):
                valid = self.repository.db.scalar(select(AnimationJob).where(
                    AnimationJob.scene_id == scene.id, AnimationJob.status == "completed",
                    AnimationJob.source_hash == animation_source(project, scene),
                ).order_by(AnimationJob.created_at.desc()))
                if valid is None or not valid.clip_path or not Path(valid.clip_path).is_file():
                    result.append(scene.id)
            return result
        assets = project.characters if stage == "characters" else project.scenes
        result = []
        for asset in assets:
            if asset.image_path:
                try:
                    local_media(project.id, asset.image_path)
                    continue
                except HTTPException:
                    pass
            result.append(asset.id)
        return result

    def state(self, project_id: int, stage: GenerationStage) -> StageGenerationState:
        project = ProjectService(self.repository).get(project_id)
        job = self.repository.db.scalar(select(Job).where(
            Job.project_id == project_id, Job.operation == stage,
        ).order_by(Job.started_at.desc().nulls_last(), Job.id.desc()))
        return StageGenerationState(
            job=JobOut(job_id=job.id, project_id=project_id, status=job.status,
                       progress=job.progress, current_stage=job.current_stage, error=job.error,
                       operation=job.operation) if job else None,
            missing=len(self.missing(project, stage)),
        )

    def start(self, project_id: int, stage: GenerationStage, *, retry: bool = False,
              review_override: str = "") -> StageGenerationState:
        self.repository.begin_write()
        self.repository.lock_project(project_id)
        project = ProjectService(self.repository).get(project_id)
        active = self.repository.db.scalar(select(Job).where(
            Job.project_id == project_id, Job.operation == stage, Job.status.in_(["queued", "running"]),
        ))
        if active:
            return self.state(project_id, stage)
        self.repository.require_no_active_job(project_id)
        if project.status == "planning" or not project.scenes or not project.story_summary:
            raise HTTPException(status_code=409, detail="Generate and review the story plan first.")
        mode = project.generation_approval.get("render_mode", "local_animation")
        if not self.approval_state(project_id, mode).approved:
            raise HTTPException(status_code=409, detail="Approve automatic stage generation estimates on Plan first.")
        if stage == "animations" and mode != "local_animation":
            return StageGenerationState(job=None, missing=0)
        stage_state = self.state(project_id, stage)
        if stage_state.job and stage_state.job.status == "failed" and not retry:
            return stage_state
        ids = self.missing(project, stage)
        if not ids:
            return stage_state
        WorkflowService.require_review(project, "story" if stage == "characters" else "characters", review_override)
        if stage == "animations":
            WorkflowService.require_review(project, "scenes", review_override)
            LocalSVDProvider().check_ready()
            if LocalSVDProvider().estimate_animation_cost()["runtime_seconds"] > project.max_wait_minutes * 60:
                raise HTTPException(status_code=422, detail="Local clip estimate exceeds the project wait limit.")
            cost = 0
        else:
            quote = AIEstimationService().estimate(
                "all_images", get_ai_configuration(self.repository.db),
                character_count=len(ids) if stage == "characters" else 0,
                scene_count=len(ids) if stage == "scenes" else 0,
            )
            if quote.estimated_minutes > project.max_wait_minutes:
                raise HTTPException(status_code=422, detail="Image batch estimate exceeds the project wait limit.")
            cost = quote.estimated_cost
        ProjectService._reserve_estimated_cost(project, cost)
        job = Job(
            id=str(uuid4()), project_id=project_id, operation=stage,
            current_stage=f"Queued {stage}", started_at=utc_now(),
            snapshot={"asset_ids": ids, "completed": [], "reserved_cost": cost,
                      "image_model": project.generation_approval["image_model"],
                      "provider": project.generation_approval["provider"]},
        )
        self.repository.db.add(job)
        project.status = f"generating_{stage}"
        self.repository.save()
        return self.state(project_id, stage)

    def run(self, job_id: str) -> None:
        self.repository.begin_write()
        job = self.repository.db.get(Job, job_id)
        if job is None or job.status != "queued":
            self.repository.db.rollback()
            return
        self.repository.lock_project(job.project_id)
        self.repository.db.refresh(job)
        if job.status != "queued":
            self.repository.db.rollback()
            return
        job.status = "running"
        self.repository.save()
        try:
            if job.operation not in ("characters", "scenes", "animations"):
                raise RuntimeError("Unknown automatic generation stage.")
            stage: GenerationStage = job.operation
            configuration = get_ai_configuration(self.repository.db)
            if (configuration.image_model != job.snapshot["image_model"]
                    or configuration.provider != job.snapshot["provider"]):
                raise RuntimeError("Provider/image model changed after batch approval. Review the new estimate before retrying.")
            provider = create_ai_provider(configuration) if stage != "animations" else None
            self.repository.db.rollback()
            ids = job.snapshot["asset_ids"]
            for index, asset_id in enumerate(ids):
                self.repository.begin_write()
                self.repository.lock_project(job.project_id)
                project = ProjectService(self.repository).get(job.project_id)
                job.current_stage = f"Generating {job.operation} {index + 1}/{len(ids)}"
                self.repository.save()
                if job.operation == "animations":
                    animation = AnimationService(self.repository)
                    state = animation.state(project.id, asset_id)
                    self.repository.db.rollback()
                    clip = animation.start(project.id, asset_id, AnimationRequest(
                        approved=True, estimate_id=state.estimate.estimate_id,
                    ), parent_job_id=job.id)
                    self.repository.db.rollback()
                    animation.run(clip.job_id)
                    finished = self.repository.db.get(AnimationJob, clip.job_id)
                    if finished is None or finished.status != "completed":
                        raise RuntimeError(finished.error if finished else "The local clip job disappeared.")
                    self.repository.db.rollback()
                else:
                    self.repository.begin_write()
                    self.repository.lock_project(project.id)
                    project = ProjectService(self.repository).get(project.id)
                    assets = project.characters if job.operation == "characters" else project.scenes
                    asset = next(item for item in assets if item.id == asset_id)
                    if asset_id in self.missing(project, stage):
                        if provider is None:
                            raise RuntimeError("Image provider is unavailable.")
                        ImageAssetService(self.repository).generate(project, asset, provider)
                    self.repository.save()
                job.snapshot = {**job.snapshot, "completed": ids[:index + 1]}
                job.progress = round(100 * (index + 1) / len(ids))
                self.repository.save()
            job.status = "completed"
            job.current_stage = "Review generated assets"
            job.completed_at = utc_now()
            ProjectService(self.repository).get(job.project_id).status = f"{job.operation}_complete"
            self.repository.save()
        except Exception as error:
            self.repository.db.rollback()
            logger.exception("Stage generation %s failed", job_id)
            job = self.repository.db.get(Job, job_id)
            if job is None:
                raise
            job.status, job.error = "failed", str(error)[:2000]
            job.current_stage = "Generation failed; explicit retry required"
            job.completed_at = utc_now()
            ProjectService(self.repository).get(job.project_id).status = f"{job.operation}_failed"
            self.repository.save()
