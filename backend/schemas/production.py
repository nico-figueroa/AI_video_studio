from typing import Literal

from pydantic import BaseModel, Field
from schemas.quality import MotionPlan


class ProductionApproval(BaseModel):
    approved: Literal[True]
    estimate_id: str = Field(min_length=64, max_length=64)


class NarrationRequest(ProductionApproval):
    regenerate: bool = False


class RenderRequest(ProductionApproval):
    resume_job_id: str | None = None
    mode: Literal["local_animation", "still_images"] = "local_animation"


class ProductionEstimate(BaseModel):
    estimate_id: str
    estimated_cost: float
    estimated_runtime_seconds: float
    estimated_storage_mb: float
    estimated_audio_seconds: float
    estimated_video_seconds: float
    estimated_api_calls: int
    model_usage: str
    notes: str = (
        "Planning estimates, not provider quotes. Local FFmpeg has no provider fee; "
        "electricity/hardware costs are excluded. Speech is AI-generated, not a cloned voice."
    )


class NarrationItem(BaseModel):
    scene_id: int
    text: str
    transition_text: str = ""
    recommended_seconds: float
    audio_url: str | None
    audio_seconds: float | None
    stale: bool


class NarrationOut(BaseModel):
    items: list[NarrationItem]
    narration_estimate: ProductionEstimate
    audio_estimate: ProductionEstimate


class TimelineItem(BaseModel):
    scene_id: int
    order: int
    title: str
    image_url: str | None
    narration: str | None
    audio_url: str | None
    audio_seconds: float | None
    duration_seconds: int
    ready: bool
    motion_plan: MotionPlan = Field(default_factory=MotionPlan)
    animation_url: str | None = None
    animation_issue: str | None = None


class TimelineOut(BaseModel):
    project_id: int
    revision: str
    scenes: list[TimelineItem]
    duration_seconds: int
    ready: bool


class TimelineChange(BaseModel):
    scene_id: int
    duration_seconds: int = Field(ge=1, le=3600)


class TimelineUpdate(BaseModel):
    revision: str = Field(min_length=64, max_length=64)
    scenes: list[TimelineChange] = Field(min_length=1, max_length=12)


class RenderStatus(BaseModel):
    job_id: str
    project_id: int
    status: str
    progress: float
    current_stage: str
    error: str | None
    completed_scenes: list[int]
    video_url: str | None
    elapsed_seconds: float = 0
    estimated_remaining_seconds: float | None = None


class VideoChapter(BaseModel):
    scene_id: int
    title: str
    start_seconds: float
    duration_seconds: float
    generated_motion_seconds: float


class ProductionVideo(BaseModel):
    url: str
    download_url: str
    duration_seconds: float | None = None
    audio_seconds: float | None = None
    size_bytes: int | None = None
    generation_seconds: float | None = None
    estimated_cost: float | None = None
    estimated_ai_spend: float
    actual_provider_cost: float | None = None
    render_job_id: str | None = None
    render_mode: str = "legacy_still_images"
    animated_scene_count: int = 0
    generated_motion_seconds: float = 0
    chapters: list[VideoChapter] = Field(default_factory=list)
    playback_audio_url: str | None = None
