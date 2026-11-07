from abc import ABC, abstractmethod
from pathlib import Path

class AnimationProvider(ABC):
    """Generated motion is separate from local camera and transition effects."""

    @abstractmethod
    def estimate_animation_cost(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def generate_character_motion(self, reference: Path, output: Path, *, seed: int = 42) -> dict:
        raise NotImplementedError

    @abstractmethod
    def generate_scene_animation(self, image: Path, output: Path, *, seed: int = 42) -> dict:
        raise NotImplementedError

    @abstractmethod
    def generate_transition_animation(self, *args, **kwargs):
        raise NotImplementedError
