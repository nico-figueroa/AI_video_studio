from typing import Literal
from pydantic import BaseModel, Field


class MotionPlan(BaseModel):
    camera: Literal["slow_zoom", "pan", "parallax"] = "slow_zoom"
    focus_x: float = Field(default=0.5, ge=0, le=1)
    focus_y: float = Field(default=0.5, ge=0, le=1)
    transition: Literal["cross_fade", "fade_black", "fade_color", "motion_blur"] = "fade_black"
    color: Literal["black", "white"] = "white"
    pacing: Literal["reflective", "balanced", "urgent"] = "balanced"
    animation_instructions: str = Field(default="", max_length=4000)
    motion_prompt: str = Field(default="", max_length=4000)
    character_movement_prompt: str = Field(default="", max_length=4000)
    execution: Literal["camera_effects_only"] = "camera_effects_only"


class NarrationScene(BaseModel):
    scene_id: int
    text: str = Field(min_length=1, max_length=3500)
    bridge: str = Field(max_length=500)


class NarrativeArc(BaseModel):
    opening: str
    development: str
    resolution: str
    scenes: list[NarrationScene]


class ReviewRequest(BaseModel):
    approved: bool
    revision: str = Field(min_length=64, max_length=64)


class ReviewState(BaseModel):
    stage: str
    approved: int
    total: int
    required_action: str


class QualityReport(BaseModel):
    score: int
    dimensions: dict[str, int]
    explanation: str = "Local context/reference coverage checks, not visual identity or semantic quality measurements."
    blockers: list[str]
    reviews: list[ReviewState]
    story_revision: str
    stage: str
    character_scores: dict[int, int] = Field(default_factory=dict)


class MotionUpdate(BaseModel):
    revision: str
    plan: MotionPlan


class TranscriptWord(BaseModel):
    word: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)


class TimedTranscript(BaseModel):
    text: str = Field(min_length=1, max_length=6000)
    words: list[TranscriptWord] = Field(min_length=1)
