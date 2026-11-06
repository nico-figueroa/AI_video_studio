from fastapi import HTTPException
from models.models import Estimate, Project
from repositories.project_repository import ProjectRepository
from services.estimation_service import EstimationService
from services.story_service import StoryService


class ProjectService:
    def __init__(self, repository: ProjectRepository):
        self.repository = repository
        self.estimation = EstimationService()

    def create(self, **values: object) -> Project:
        return self.repository.create_project(**values)

    def get(self, project_id: int) -> Project:
        project = self.repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        return project

    def analyze(self, project_id: int, *, refresh: bool = False) -> Project:
        self.repository.begin_write()
        self.repository.require_no_active_job(project_id)
        project = self.get(project_id)
        StoryService(self.repository).analyze(project, refresh=refresh)
        if refresh or not project.estimates:
            project.estimates.clear()
            for values in self.estimation.calculate(project, len(project.scenes)):
                project.estimates.append(Estimate(**values))
        self.repository.save()
        return self.get(project_id)

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
