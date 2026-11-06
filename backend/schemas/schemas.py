from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PlanName = Literal["economy", "balanced", "premium"]
MAX_STORY_TITLE_LENGTH = 160


class ProjectCreate(BaseModel):
    prompt: str = Field(min_length=12, max_length=4000)
    target_minutes: int = Field(default=1, ge=1, le=10)
    max_budget: float = Field(default=5.0, ge=0, le=1000)
    max_wait_minutes: int = Field(default=20, ge=1, le=1440)


class ProjectCreated(BaseModel):
    project_id: int
    status: str


class ProjectSummary(BaseModel):
    id: int
    title: str
    status: str
    target_minutes: int
    selected_plan: str | None
    created_at: datetime
    estimated_cost: float | None = None


class ProjectDetail(ProjectSummary):
    prompt: str
    max_budget: float
    max_wait_minutes: int
    video_url: str | None = None


class CharacterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    image_path: str | None
    approved: bool


class CharacterUpdate(BaseModel):
    approved: bool


class SceneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scene_number: int
    title: str
    description: str
    image_path: str | None
    status: str
    approved: bool


class SceneUpdate(BaseModel):
    approved: bool


class StoryOut(BaseModel):
    title: str
    summary: str
    characters: list[CharacterOut]
    scenes: list[SceneOut]


class StoryUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=MAX_STORY_TITLE_LENGTH)
    summary: str = Field(min_length=1, max_length=6000)
    characters: list[CharacterOut]
    scenes: list[SceneOut]


class StoryUpdated(BaseModel):
    updated: bool


class EstimateOut(BaseModel):
    plan_name: PlanName
    estimated_cost: float
    estimated_minutes: int
    resolution: str
    quality_score: int
    storage_mb: float
    gpu_minutes: float


class EstimateComparison(BaseModel):
    economy: EstimateOut
    balanced: EstimateOut
    premium: EstimateOut
    simulated: bool = True
    actual_provider_cost: float = 0.0


class PlanSelection(BaseModel):
    plan: PlanName


class PlanSelected(BaseModel):
    selected_plan: PlanName


class StatusOut(BaseModel):
    status: str


class VideoRequest(BaseModel):
    plan: PlanName


class VideoQueued(BaseModel):
    job_id: str
    status: str


class JobOut(BaseModel):
    job_id: str
    project_id: int
    status: str
    progress: int
    current_stage: str
    error: str | None = None
    video_url: str | None = None


class VideoLink(BaseModel):
    url: str


class MetricsOut(BaseModel):
    estimated_cost: float
    actual_cost: float
    estimated_time: int
    actual_time: int | None
    total_images: int
    video_length_seconds: int | None
