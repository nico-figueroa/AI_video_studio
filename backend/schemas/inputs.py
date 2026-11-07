from typing import Literal
from pydantic import BaseModel, Field
from schemas.ai_schemas import CharacterBibleData
from schemas.production import ProductionApproval


class SuppliedScene(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=4000)
    duration_seconds: int = Field(default=15, ge=1, le=3600)


class SuppliedFile(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    content_base64: str = Field(min_length=1, max_length=28_000_000)
    description: str = Field(default="", max_length=4000)


class InputBundle(BaseModel):
    text: str = Field(default="", max_length=6000)
    text_kind: Literal["auto", "text_story", "scene_descriptions", "narration_script", "character_definitions"] = "auto"
    title: str = Field(default="Imported story", min_length=1, max_length=160)
    scenes: list[SuppliedScene] = Field(default_factory=list, max_length=12)
    characters: list[CharacterBibleData] = Field(default_factory=list, max_length=12)
    images: list[SuppliedFile] = Field(default_factory=list, max_length=12)
    audio: SuppliedFile | None = None
    documents: list[SuppliedFile] = Field(default_factory=list, max_length=12)


class InputClassification(BaseModel):
    kinds: list[str]
    workflow: list[str]
    preserved: list[str]
    limitations: list[str]
    needs_transcription: bool


class InputState(BaseModel):
    classification: InputClassification
    manifest: dict


class TranscriptionRequest(ProductionApproval):
    pass
