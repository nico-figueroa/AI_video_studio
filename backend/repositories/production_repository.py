from sqlalchemy import select

from models.models import Narration, RenderJob, Video
from repositories.project_repository import ProjectRepository


class ProductionRepository(ProjectRepository):
    def narrations(self, project_id: int) -> list[Narration]:
        return list(self.db.scalars(select(Narration).where(Narration.project_id == project_id)))

    def latest_job(self, project_id: int) -> RenderJob | None:
        return self.db.scalar(
            select(RenderJob).where(RenderJob.project_id == project_id)
            .order_by(RenderJob.created_at.desc()).limit(1)
        )

    def render_job(self, job_id: str) -> RenderJob | None:
        return self.db.get(RenderJob, job_id)

    def latest_video(self, project_id: int) -> Video | None:
        return self.db.scalar(
            select(Video).where(Video.project_id == project_id)
            .order_by(Video.created_at.desc(), Video.id.desc()).limit(1)
        )

    def add(self, entity: Narration | RenderJob | Video) -> None:
        self.db.add(entity)
