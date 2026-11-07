import logging
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from models.models import AnimationJob, GeneratedAsset, Job, Narration, RenderJob, Video
from repositories.project_repository import ProjectRepository
from schemas.schemas import ProjectRestart
from services.project_service import ProjectService
import services.image_service as media

logger = logging.getLogger(__name__)


class ProjectLifecycleService:
    def __init__(self, repository: ProjectRepository):
        self.repository = repository

    def change(self, project_id: int, *, restart: ProjectRestart | None = None,
               videos_only: bool = False) -> None:
        db = self.repository.db
        self.repository.begin_write()
        self.repository.lock_project(project_id)
        self.repository.require_no_active_job(project_id)
        project = ProjectService(self.repository).get(project_id)
        if project.status == "planning":
            raise HTTPException(status_code=409, detail="Wait for planning to finish before deleting or restarting.")
        if restart and restart.expected_prompt != project.prompt:
            raise HTTPException(status_code=409, detail="The original prompt changed. Reload before restarting.")

        root = media.STORAGE_DIR.resolve()
        directory = root / "projects" / str(project_id)
        targets = ([*directory.glob("video-*.mp4"), *directory.glob("render-*")]
                   if videos_only else [directory])
        # Never follow redirected project directories or media into another project's storage.
        for target in targets:
            if target.is_symlink() or target.resolve() != target.absolute() or not target.resolve().is_relative_to(directory):
                raise HTTPException(status_code=409, detail="Unsafe project media path. Deletion requires manual review.")
        staged = root / "pending-deletions" / uuid4().hex
        if staged.parent.resolve() != staged.parent.absolute():
            raise HTTPException(status_code=409, detail="Unsafe deletion staging directory. Manual review is required.")
        moved: list[tuple[Path, Path]] = []
        try:
            for target in targets:
                if target.exists():
                    staged.mkdir(parents=True, exist_ok=True)
                    destination = staged / target.name
                    target.rename(destination)
                    moved.append((target, destination))
            db.query(Video).filter_by(project_id=project_id).delete(synchronize_session=False)
            db.query(RenderJob).filter_by(project_id=project_id).delete(synchronize_session=False)
            if videos_only:
                db.query(GeneratedAsset).filter_by(project_id=project_id, asset_type="video").delete(synchronize_session=False)
                db.query(Job).filter_by(project_id=project_id, operation="legacy_video").delete(synchronize_session=False)
                project.video_path = None
                project.status = "video_deleted"
            else:
                for model in (AnimationJob, Narration, GeneratedAsset, Job):
                    db.query(model).filter_by(project_id=project_id).delete(synchronize_session=False)
                if restart:
                    project.characters.clear()
                    project.scenes.clear()
                    project.estimates.clear()
                    project.prompt = restart.prompt
                    project.target_minutes = restart.target_seconds / 60
                    project.max_budget = restart.max_budget
                    project.max_wait_minutes = restart.max_wait_minutes
                    project.title = "Untitled project"
                    project.story_summary = project.genre = project.target_audience = ""
                    project.three_act_structure = {}
                    project.input_manifest = {}
                    project.narration_arc = {}
                    project.narrative_analysis = {}
                    project.review_overrides = []
                    project.generation_approval = {}
                    project.story_approved = False
                    project.selected_plan = project.video_path = None
                    project.status = "created"
                    # Historical spending is not refunded by deleting content.
                else:
                    db.delete(project)
            self.repository.save()
        except Exception as error:
            db.rollback()
            for original, destination in reversed(moved):
                if destination.exists():
                    destination.rename(original)
            logger.exception("Project %s deletion/restart failed", project_id)
            if isinstance(error, OSError):
                raise HTTPException(status_code=409, detail=(
                    "Could not move project media; no database changes were saved. "
                    "Close applications using these files and retry."
                )) from error
            raise
        if staged.exists():
            try:
                shutil.rmtree(staged)
            except OSError as error:
                logger.exception("Project %s media cleanup remains pending at %s", project_id, staged)
                raise HTTPException(status_code=500, detail=(
                    "Database changes completed, but media cleanup failed. Files remain in private "
                    "pending-deletions storage; inspect backend logs before retrying."
                )) from error
