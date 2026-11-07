from datetime import datetime
import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from services.ai.estimation_service import GenerationEstimate


PlanName = Literal["economy", "balanced", "premium"]
ProviderName = Literal["openai"]
MAX_STORY_TITLE_LENGTH = 160


def _default_budget() -> float:
    return float(os.getenv("DEFAULT_MAX_PROJECT_BUDGET", "5.00"))


def _default_wait_minutes() -> int:
    return int(os.getenv("DEFAULT_MAX_WAIT_MINUTES", "20"))


class ProjectCreate(BaseModel):
    prompt: str = Field(min_length=12, max_length=4000)
    target_minutes: float = Field(default=1, ge=1 / 60, le=10)
    target_seconds: int | None = Field(default=None, ge=1, le=600)
    max_budget: float = Field(default_factory=_default_budget, ge=0, le=1000)
    max_wait_minutes: int = Field(default_factory=_default_wait_minutes, ge=1, le=1440)

    @model_validator(mode="after")
    def normalize_duration(self):
        if self.target_seconds is not None:
            if "target_minutes" in self.model_fields_set and round(self.target_minutes * 60) != self.target_seconds:
                raise ValueError("Supply matching target_seconds and target_minutes, or use only target_seconds.")
            self.target_minutes = self.target_seconds / 60
        elif abs(self.target_minutes * 60 - round(self.target_minutes * 60)) > 1e-6:
            raise ValueError("Target length must be a whole number of seconds.")
        return self


class ProjectRestart(BaseModel):
    approved: Literal[True]
    expected_prompt: str
    prompt: str = Field(min_length=12, max_length=4000)
    target_seconds: int = Field(ge=1, le=600)
    max_budget: float = Field(ge=0, le=1000)
    max_wait_minutes: int = Field(ge=1, le=1440)


class DeletionApproval(BaseModel):
    approved: Literal[True]


class ProjectCreated(BaseModel):
    project_id: int
    status: str


class ProjectSummary(BaseModel):
    id: int
    title: str
    status: str
    target_minutes: float
    target_seconds: int
    selected_plan: str | None
    created_at: datetime
    estimated_cost: float | None = None


class ProjectDetail(ProjectSummary):
    prompt: str
    max_budget: float
    max_wait_minutes: int
    estimated_spend: float
    video_url: str | None = None
    render_mode: Literal["local_animation", "still_images"] = "local_animation"


class CharacterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str = Field(min_length=1, max_length=120)
    description: str
    role: str
    personality: str
    appearance: str
    motivations: str
    relationships: str
    portrait_prompt: str
    image_path: str | None
    approved: bool
    clothing: str = ""
    age: str = Field(default="", max_length=120)
    distinctive_traits: str = ""
    negative_prompt: str = ""
    facial_features: str = ""
    reference_image_paths: list[str] = Field(default_factory=list)
    generation_context: dict = Field(default_factory=dict)


class CharacterUpdate(BaseModel):
    approved: bool
    expected_image_path: str | None


class SceneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scene_number: int
    title: str = Field(min_length=1, max_length=160)
    description: str
    visual_description: str
    image_prompt: str
    estimated_duration: int = Field(ge=1, le=3600)
    image_path: str | None
    status: str
    approved: bool
    motion_plan: dict = Field(default_factory=dict)
    generation_context: dict = Field(default_factory=dict)
    beat_number: int = 1


class SceneUpdate(BaseModel):
    approved: bool
    expected_image_path: str | None


class StoryOut(BaseModel):
    title: str
    summary: str
    genre: str
    target_audience: str
    three_act_structure: dict[str, str]
    characters: list[CharacterOut]
    scenes: list[SceneOut]


class StoryUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=MAX_STORY_TITLE_LENGTH)
    summary: str = Field(min_length=1, max_length=6000)
    genre: str = Field(default="", max_length=120)
    target_audience: str = Field(default="", max_length=240)
    three_act_structure: dict[str, str] = Field(default_factory=dict)
    characters: list[CharacterOut]
    scenes: list[SceneOut]


class StoryUpdated(BaseModel):
    updated: bool
    revision: str


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
    operation: str = "legacy_video"


class VideoLink(BaseModel):
    url: str


class MetricsOut(BaseModel):
    estimated_cost: float
    actual_cost: float
    estimated_ai_spend: float
    actual_provider_cost: float | None = None
    estimated_time: int
    actual_time: int | None
    total_images: int
    video_length_seconds: float | None


class AISettingsOut(BaseModel):
    provider: ProviderName
    model: str
    image_model: str
    default_budget: float
    default_wait_minutes: int
    api_key_configured: bool


class AISettingsUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    provider: ProviderName
    model: str = Field(min_length=1, max_length=120)
    image_model: str = Field(min_length=1, max_length=120)
    default_budget: float = Field(ge=0, le=1000)
    default_wait_minutes: int = Field(ge=1, le=1440)


class GenerationEstimatesOut(BaseModel):
    planning: GenerationEstimate
    story: GenerationEstimate
    characters: GenerationEstimate
    scenes: GenerationEstimate
    character_portrait: GenerationEstimate
    scene_image: GenerationEstimate
    all_images: GenerationEstimate
