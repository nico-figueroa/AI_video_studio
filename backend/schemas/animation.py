from pydantic import BaseModel, Field

from schemas.production import ProductionApproval, ProductionEstimate


class AnimationRequest(ProductionApproval):
    seed: int = Field(default=42, ge=0, le=2147483647)


class AnimationReview(BaseModel):
    job_id: str
    approved: bool


class AnimationStatus(BaseModel):
    job_id: str
    scene_id: int
    status: str
    progress: int
    error: str | None
    clip_url: str | None
    approved: bool
    stale: bool
    metadata: dict


class AnimationState(BaseModel):
    estimate: ProductionEstimate
    job: AnimationStatus | None
