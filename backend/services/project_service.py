import logging
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from database import STORAGE_DIR
from models.models import AIConfiguration, Estimate, Job, Project
from repositories.project_repository import ProjectRepository
from services.ai.configuration import create_ai_provider, get_ai_configuration
from services.ai.estimation_service import AIEstimationService
from services.ai.providers.base import AIProvider
from services.estimation_service import EstimationService
from services.story_service import StoryService

logger = logging.getLogger(__name__)


class ProjectService:
    def __init__(self, repository: ProjectRepository):
        self.repository = repository
        self.estimation = EstimationService()
        self.ai_estimation = AIEstimationService()

    def create(self, **values: object) -> Project:
        return self.repository.create_project(**values)

    def get(self, project_id: int) -> Project:
        project = self.repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        return project

    def analyze(
        self,
        project_id: int,
        *,
        refresh: bool = False,
        provider: AIProvider | None = None,
    ) -> Project:
        self.repository.begin_write()
        self.repository.lock_project(project_id)
        self.repository.require_no_active_job(project_id)
        project = self.get(project_id)
        if project.status == "planning":
            raise HTTPException(status_code=409, detail="Story planning is already running for this project.")
        if project.scenes and not refresh:
            return project
        if provider is None:
            provider = create_ai_provider(get_ai_configuration(self.repository.db))
        configuration = get_ai_configuration(self.repository.db)
        scene_count = self.ai_estimation.scene_count_for(project.target_minutes)
        planning_estimate = self.ai_estimation.estimate_all(
            configuration, character_count=3, scene_count=scene_count
        )[0]
        previous_status = project.status
        self._reserve_estimated_cost(project, planning_estimate.estimated_cost)
        project.status = "planning"
        self.repository.save()
        try:
            self.repository.begin_write()
            self.repository.lock_project(project_id)
            self.repository.require_no_active_job(project_id)
            project = self.get(project_id)
            obsolete = self._media_paths(project) if refresh else set()
            StoryService(self.repository).analyze(project, provider, refresh=refresh)
            if refresh or not project.estimates:
                project.estimates.clear()
                for values in self.estimation.calculate(project, len(project.scenes)):
                    project.estimates.append(Estimate(**values))
            self.repository.save()
        except (HTTPException, RuntimeError, SQLAlchemyError, ValueError):
            self.repository.db.rollback()
            failed_project = self.repository.get_project(project_id)
            if failed_project is not None:
                failed_project.status = previous_status
                self.repository.db.commit()
            raise
        if obsolete:
            self._remove_obsolete_media(project_id, obsolete)
        return self.get(project_id)

    @staticmethod
    def _reserve_estimated_cost(project: Project, cost: float) -> None:
        if project.estimated_spend + cost > project.max_budget:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"This generation is estimated at ${cost:.4f}, which would exceed the "
                    f"remaining project budget of ${max(0, project.max_budget - project.estimated_spend):.4f}."
                ),
            )
        project.estimated_spend = round(project.estimated_spend + cost, 4)

    @staticmethod
    def _media_paths(project: Project) -> set[Path]:
        directory = STORAGE_DIR / "projects" / str(project.id)
        paths = set(directory.glob("character-*.png"))
        paths.update(directory.glob("scene-*.png"))
        paths.update(directory.glob("video-*.mp4"))
        paths.update(directory / f"character-{character.id}.png" for character in project.characters)
        paths.update(directory / f"scene-{scene.id}.png" for scene in project.scenes)
        if project.video_path:
            paths.add(Path(project.video_path))
        return paths

    def _remove_obsolete_media(self, project_id: int, obsolete: set[Path]) -> None:
        self.repository.begin_write()
        try:
            self.repository.db.expire_all()
            active = self.repository.db.query(Job).filter(
                Job.project_id == project_id, Job.status.in_(["queued", "running"])
            ).first()
            if active:
                logger.info("Skipping obsolete media cleanup for project %s during an export", project_id)
                return
            project = self.get(project_id)
            directory = STORAGE_DIR / "projects" / str(project_id)
            current = {
                directory / f"character-{character.id}.png"
                for character in project.characters if character.image_path
            }
            current.update(
                directory / f"scene-{scene.id}.png"
                for scene in project.scenes if scene.image_path
            )
            if project.video_path:
                current.add(Path(project.video_path))
            for path in obsolete - current:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    logger.exception("Could not remove obsolete project media %s", path)
        finally:
            self.repository.db.rollback()

    def select_plan(self, project_id: int, plan: str, *, commit: bool = True) -> Estimate:
        if commit:
            self.repository.begin_write()
        self.repository.require_no_active_job(project_id)
        project = self.get(project_id)
        if not project.estimates:
            raise HTTPException(status_code=409, detail="Analyze the project before selecting a plan.")
        estimate = next((item for item in project.estimates if item.plan_name == plan), None)
        if estimate is None:
            raise HTTPException(status_code=404, detail="Estimate not found.")
        if estimate.estimated_cost > project.max_budget:
            raise HTTPException(
                status_code=422,
                detail=f"This plan exceeds your ${project.max_budget:.2f} budget limit.",
            )
        if estimate.estimated_minutes > project.max_wait_minutes:
            raise HTTPException(
                status_code=422,
                detail=f"This plan exceeds your {project.max_wait_minutes} minute wait limit.",
            )
        project.selected_plan = plan
        project.status = "plan_selected"
        if commit:
            self.repository.save()
        return estimate
