from typing import Literal

from pydantic import BaseModel

from schemas.production import ProductionApproval, ProductionEstimate
from schemas.schemas import JobOut

GenerationStage = Literal["characters", "scenes", "animations"]
RenderMode = Literal["local_animation", "still_images"]


class AutomaticGenerationApproval(ProductionApproval):
    render_mode: RenderMode = "local_animation"


class StageGenerationRequest(BaseModel):
    retry: bool = False


class AutomaticGenerationState(BaseModel):
    estimate: ProductionEstimate
    approved: bool
    render_mode: RenderMode
    characters: int
    scenes: int
    max_animation_seconds: float


class StageGenerationState(BaseModel):
    job: JobOut | None
    missing: int
