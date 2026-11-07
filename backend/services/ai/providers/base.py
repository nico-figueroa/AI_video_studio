from abc import ABC, abstractmethod
from pathlib import Path

from schemas.ai_schemas import CharacterBible, NarrativeScenePlan, ScenePlan, StoryBibleData
from schemas.quality import NarrativeArc, TimedTranscript


class AIProviderError(RuntimeError):
    """Raised when a provider cannot produce or validate a requested result."""


class AIProviderConfigurationError(AIProviderError):
    """Raised when the selected provider is not ready to accept requests."""


class AIProvider(ABC):
    def generate_narrative_plan(self, story: StoryBibleData, characters: CharacterBible,
                                target_minutes: float) -> NarrativeScenePlan | None:
        return None

    def compose_narration(self, context: dict) -> NarrativeArc:
        raise AIProviderError("This provider does not support coherent narration composition.")

    def transcribe_audio(self, path: Path) -> str:
        raise AIProviderError("This provider does not support audio transcription.")

    def transcribe_audio_timed(self, path: Path) -> TimedTranscript:
        raise AIProviderError("This provider does not support timestamp-aligned audio transcription.")

    def generate_consistent_image(self, prompt: str, output_path: Path, references: list[Path]) -> Path:
        raise AIProviderError("This provider does not support reference-conditioned image generation.")

    @abstractmethod
    def generate_narration(self, title: str, description: str, seconds: int) -> str:
        raise AIProviderError("This provider does not support narration generation.")

    @abstractmethod
    def generate_speech(self, text: str, output_path: Path) -> Path:
        raise AIProviderError("This provider does not support speech generation.")

    @abstractmethod
    def generate_story(self, prompt: str, target_minutes: float) -> StoryBibleData:
        raise NotImplementedError

    @abstractmethod
    def generate_character_bible(self, story: StoryBibleData) -> CharacterBible:
        raise NotImplementedError

    @abstractmethod
    def generate_scene_plan(
        self,
        story: StoryBibleData,
        characters: CharacterBible,
        target_minutes: float,
    ) -> ScenePlan:
        raise NotImplementedError

    @abstractmethod
    def generate_character_portrait(self, prompt: str, output_path: Path) -> Path:
        raise NotImplementedError

    @abstractmethod
    def generate_scene_image(self, prompt: str, output_path: Path) -> Path:
        raise NotImplementedError
