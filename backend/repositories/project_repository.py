from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from models.models import Character, Estimate, GeneratedAsset, Job, Project, Scene


class ProjectRepository:
    def __init__(self, db: Session):
        self.db = db

    def begin_write(self) -> None:
        if self.db.get_bind().dialect.name == "sqlite":
            self.db.execute(text("BEGIN IMMEDIATE"))
        elif not self.db.in_transaction():
            self.db.begin()

    def require_no_active_job(self, project_id: int) -> None:
        active = self.db.query(Job).filter(
            Job.project_id == project_id, Job.status.in_(["queued", "running"])
        ).first()
        if active:
            raise HTTPException(status_code=409, detail="A generation job is already running for this project.")

    def lock_project(self, project_id: int) -> None:
        self.db.scalar(
            select(Project)
            .where(Project.id == project_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def create_project(self, **values: object) -> Project:
        project = Project(**values)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def get_project(self, project_id: int) -> Project | None:
        return self.db.scalar(
            select(Project)
            .options(
                selectinload(Project.characters),
                selectinload(Project.scenes),
                selectinload(Project.estimates),
            )
            .where(Project.id == project_id)
            .execution_options(populate_existing=True)
        )

    def list_projects(self) -> list[Project]:
        return list(self.db.scalars(
            select(Project).options(selectinload(Project.estimates)).order_by(Project.created_at.desc())
        ))

    def save(self) -> None:
        self.db.commit()

    def add_character(self, **values: object) -> Character:
        character = Character(**values)
        self.db.add(character)
        self.db.flush()
        return character

    def add_scene(self, **values: object) -> Scene:
        scene = Scene(**values)
        self.db.add(scene)
        self.db.flush()
        return scene

    def add_estimate(self, **values: object) -> Estimate:
        estimate = Estimate(**values)
        self.db.add(estimate)
        self.db.flush()
        return estimate

    def add_asset(self, **values: object) -> GeneratedAsset:
        asset = GeneratedAsset(**values)
        self.db.add(asset)
        self.db.flush()
        return asset

    def clear_assets(self, project_id: int) -> None:
        self.db.query(GeneratedAsset).filter(
            GeneratedAsset.project_id == project_id
        ).delete(synchronize_session=False)

    def get_character(self, character_id: int) -> Character | None:
        return self.db.scalar(
            select(Character)
            .where(Character.id == character_id)
            .execution_options(populate_existing=True)
        )

    def get_scene(self, scene_id: int) -> Scene | None:
        return self.db.scalar(
            select(Scene)
            .where(Scene.id == scene_id)
            .execution_options(populate_existing=True)
        )

    def get_job(self, job_id: str) -> Job | None:
        return self.db.get(Job, job_id)

    def create_job(self, **values: object) -> Job:
        job = Job(**values)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def update_job(self, job_id: str, **values: object) -> Job | None:
        job = self.get_job(job_id)
        if job is None:
            return None
        for key, value in values.items():
            setattr(job, key, value)
        self.db.commit()
        self.db.refresh(job)
        return job
