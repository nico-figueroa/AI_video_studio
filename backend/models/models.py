from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160), default="Untitled project")
    prompt: Mapped[str] = mapped_column(Text)
    story_summary: Mapped[str] = mapped_column(Text, default="")
    genre: Mapped[str] = mapped_column(String(120), default="")
    target_audience: Mapped[str] = mapped_column(String(240), default="")
    three_act_structure: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="created")
    target_minutes: Mapped[int] = mapped_column(Integer, default=1)
    max_budget: Mapped[float] = mapped_column(Float, default=5.0)
    max_wait_minutes: Mapped[int] = mapped_column(Integer, default=20)
    selected_plan: Mapped[str | None] = mapped_column(String(20), nullable=True)
    video_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    actual_cost: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_spend: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    characters: Mapped[list["Character"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    scenes: Mapped[list["Scene"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    estimates: Mapped[list["Estimate"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, default="")
    personality: Mapped[str] = mapped_column(Text, default="")
    appearance: Mapped[str] = mapped_column(Text, default="")
    motivations: Mapped[str] = mapped_column(Text, default="")
    relationships: Mapped[str] = mapped_column(Text, default="")
    portrait_prompt: Mapped[str] = mapped_column(Text, default="")
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    approved: Mapped[bool] = mapped_column(default=False)
    project: Mapped[Project] = relationship(back_populates="characters")


class Scene(Base):
    __tablename__ = "scenes"
    __table_args__ = (
        UniqueConstraint("project_id", "scene_number", name="uq_scenes_project_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    scene_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    visual_description: Mapped[str] = mapped_column(Text, default="")
    image_prompt: Mapped[str] = mapped_column(Text, default="")
    estimated_duration: Mapped[int] = mapped_column(Integer, default=30)
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    approved: Mapped[bool] = mapped_column(default=False)
    project: Mapped[Project] = relationship(back_populates="scenes")


class Estimate(Base):
    __tablename__ = "estimates"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    plan_name: Mapped[str] = mapped_column(String(20))
    estimated_cost: Mapped[float] = mapped_column(Float)
    estimated_minutes: Mapped[int] = mapped_column(Integer)
    resolution: Mapped[str] = mapped_column(String(30))
    quality_score: Mapped[int] = mapped_column(Integer)
    storage_mb: Mapped[float] = mapped_column(Float)
    gpu_minutes: Mapped[float] = mapped_column(Float)
    project: Mapped[Project] = relationship(back_populates="estimates")


class GeneratedAsset(Base):
    __tablename__ = "generated_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    asset_type: Mapped[str] = mapped_column(String(40))
    file_path: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index(
            "uq_jobs_active_project",
            "project_id",
            unique=True,
            sqlite_where=text("status IN ('queued', 'running')"),
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    current_stage: Mapped[str] = mapped_column(String(60), default="queued")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AIConfiguration(Base):
    __tablename__ = "ai_configuration"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    provider: Mapped[str] = mapped_column(String(40), default="openai")
    model: Mapped[str] = mapped_column(String(120), default="gpt-5")
    image_model: Mapped[str] = mapped_column(String(120), default="gpt-image-1")
    default_budget: Mapped[float] = mapped_column(Float, default=5.0)
    default_wait_minutes: Mapped[int] = mapped_column(Integer, default=20)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
