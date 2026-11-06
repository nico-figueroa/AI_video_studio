from abc import ABC, abstractmethod
from pathlib import Path

from schemas.ai_schemas import CharacterBible, ScenePlan, StoryBibleData


class AIProviderError(RuntimeError):
    """Raised when a provider cannot produce or validate a requested result."""


class AIProviderConfigurationError(AIProviderError):
    """Raised when the selected provider is not ready to accept requests."""


class AIProvider(ABC):
    @abstractmethod
    def generate_story(self, prompt: str, target_minutes: int) -> StoryBibleData:
        raise NotImplementedError

    @abstractmethod
    def generate_character_bible(self, story: StoryBibleData) -> CharacterBible:
        raise NotImplementedError

    @abstractmethod
    def generate_scene_plan(
        self,
        story: StoryBibleData,
        characters: CharacterBible,
        target_minutes: int,
    ) -> ScenePlan:
        raise NotImplementedError

    @abstractmethod
    def generate_character_portrait(self, prompt: str, output_path: Path) -> Path:
        raise NotImplementedError

    @abstractmethod
    def generate_scene_image(self, prompt: str, output_path: Path) -> Path:
        raise NotImplementedError
