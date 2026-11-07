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
    target_minutes: Mapped[float] = mapped_column(Float, default=1)
    max_budget: Mapped[float] = mapped_column(Float, default=5.0)
    max_wait_minutes: Mapped[int] = mapped_column(Integer, default=20)
    selected_plan: Mapped[str | None] = mapped_column(String(20), nullable=True)
    video_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    actual_cost: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_spend: Mapped[float] = mapped_column(Float, default=0.0)
    story_approved: Mapped[bool] = mapped_column(default=False)
    input_manifest: Mapped[dict] = mapped_column(JSON, default=dict)
    narration_arc: Mapped[dict] = mapped_column(JSON, default=dict)
    review_overrides: Mapped[list[dict]] = mapped_column(JSON, default=list)
    narrative_analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    generation_approval: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    @property
    def target_seconds(self) -> int:
        return round(self.target_minutes * 60)

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
    clothing: Mapped[str] = mapped_column(Text, default="")
    age: Mapped[str] = mapped_column(String(120), default="")
    distinctive_traits: Mapped[str] = mapped_column(Text, default="")
    negative_prompt: Mapped[str] = mapped_column(Text, default="")
    facial_features: Mapped[str] = mapped_column(Text, default="")
    reference_image_paths: Mapped[list[str]] = mapped_column(JSON, default=list)
    generation_context: Mapped[dict] = mapped_column(JSON, default=dict)
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
    motion_plan: Mapped[dict] = mapped_column(JSON, default=dict)
    generation_context: Mapped[dict] = mapped_column(JSON, default=dict)
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    beat_number: Mapped[int] = mapped_column(Integer, default=1)
    approved: Mapped[bool] = mapped_column(default=False)
    project: Mapped[Project] = relationship(back_populates="scenes")
    narration: Mapped["Narration | None"] = relationship(
        cascade="all, delete-orphan", single_parent=True
    )


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
    operation: Mapped[str] = mapped_column(String(40), default="legacy_video")
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
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


class AnimationJob(Base):
    __tablename__ = "animation_jobs"
    __table_args__ = (
        Index(
            "uq_animation_gpu_active", "gpu_slot", unique=True,
            sqlite_where=text("status IN ('queued', 'running')"),
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    scene_id: Mapped[int] = mapped_column(ForeignKey("scenes.id", ondelete="CASCADE"), index=True)
    gpu_slot: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    source_hash: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSON)
    result_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    clip_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    approved: Mapped[bool] = mapped_column(default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Narration(Base):
    __tablename__ = "narrations"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    scene_id: Mapped[int] = mapped_column(ForeignKey("scenes.id", ondelete="CASCADE"), unique=True)
    text: Mapped[str] = mapped_column(Text)
    transition_text: Mapped[str] = mapped_column(Text, default="")
    source_hash: Mapped[str] = mapped_column(String(64))
    recommended_seconds: Mapped[float] = mapped_column(Float)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(120))
    audio_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    audio_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    speech_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    voice: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RenderJob(Base):
    __tablename__ = "render_jobs"
    __table_args__ = (
        Index(
            "uq_render_jobs_active_project", "project_id", unique=True,
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
    timeline_hash: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSON)
    completed_scenes: Mapped[list[int]] = mapped_column(JSON, default=list)
    execution_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    render_job_id: Mapped[str] = mapped_column(ForeignKey("render_jobs.id"), unique=True)
    file_path: Mapped[str] = mapped_column(String(500))
    duration_seconds: Mapped[float] = mapped_column(Float)
    audio_seconds: Mapped[float] = mapped_column(Float)
    size_bytes: Mapped[int] = mapped_column(Integer)
    generation_seconds: Mapped[float] = mapped_column(Float)
    estimated_cost: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
