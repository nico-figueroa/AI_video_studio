import math
import os
from dataclasses import asdict, dataclass

from models.models import AIConfiguration


@dataclass(frozen=True)
class GenerationEstimate:
    operation: str
    estimated_cost: float
    estimated_minutes: float
    estimated_model_usage: str
    estimated_api_calls: int
    notes: str

    def as_dict(self) -> dict[str, str | float | int]:
        return asdict(self)


class AIEstimationService:
    def __init__(self) -> None:
        self.text_usd_per_1k_tokens = float(os.getenv("ESTIMATED_TEXT_USD_PER_1K_TOKENS", "0.002"))
        self.image_usd_per_image = float(os.getenv("ESTIMATED_IMAGE_USD_PER_IMAGE", "0.04"))

    def estimate(
        self,
        operation: str,
        configuration: AIConfiguration,
        *,
        character_count: int = 0,
        scene_count: int = 0,
    ) -> GenerationEstimate:
        input_tokens = 1200
        output_tokens = 1000
        image_count = 0
        calls = 1
        minutes = 1.0
        if operation == "story":
            input_tokens, output_tokens = 1200, 1000
        elif operation == "characters":
            input_tokens = 900 + max(1, character_count) * 150
            output_tokens = max(1, character_count) * 700 + 100
        elif operation == "scenes":
            input_tokens = 1400 + max(1, character_count) * 250
            output_tokens = max(1, scene_count) * 400
        elif operation == "character_portrait":
            image_count = 1
            minutes = 1.5
        elif operation == "scene_image":
            image_count = 1
            minutes = 1.5
        elif operation == "all_images":
            image_count = character_count + scene_count
            calls = image_count
            minutes = max(1.0, image_count * 1.5)
        else:
            raise ValueError(f"Unknown generation operation: {operation}")

        text_cost = ((input_tokens + output_tokens) / 1000) * self.text_usd_per_1k_tokens
        cost = text_cost + image_count * self.image_usd_per_image
        if operation == "characters":
            minutes = 1.0
        elif operation == "scenes":
            minutes = 1.0

        if operation in {"character_portrait", "scene_image"}:
            model_usage = f"1 image using {configuration.image_model}"
        elif operation == "all_images":
            model_usage = f"{image_count} images using {configuration.image_model}"
        else:
            model_usage = (
                f"About {input_tokens:,} input and {output_tokens:,} output tokens "
                f"using {configuration.model}"
            )
        return GenerationEstimate(
            operation=operation,
            estimated_cost=round(cost, 4),
            estimated_minutes=round(minutes, 1),
            estimated_model_usage=model_usage,
            estimated_api_calls=calls,
            notes="Planning estimate only; actual provider billing and response time may differ.",
        )

    def estimate_all(
        self, configuration: AIConfiguration, character_count: int, scene_count: int
    ) -> list[GenerationEstimate]:
        story = self.estimate("story", configuration)
        characters = self.estimate("characters", configuration, character_count=character_count)
        scenes = self.estimate(
            "scenes", configuration, character_count=character_count, scene_count=scene_count
        )
        character_portrait = self.estimate("character_portrait", configuration)
        scene_image = self.estimate("scene_image", configuration)
        all_images = self.estimate(
            "all_images", configuration, character_count=character_count, scene_count=scene_count
        )
        planning = GenerationEstimate(
            operation="planning",
            estimated_cost=round(
                story.estimated_cost + characters.estimated_cost + scenes.estimated_cost, 4
            ),
            estimated_minutes=round(
                story.estimated_minutes + characters.estimated_minutes + scenes.estimated_minutes, 1
            ),
            estimated_model_usage=(
                f"3 text calls using {configuration.model}; estimated tokens are shown per stage"
            ),
            estimated_api_calls=3,
            notes="Planning estimate only; actual provider billing and response time may differ.",
        )
        return [
            planning,
            story,
            characters,
            scenes,
            character_portrait,
            scene_image,
            all_images,
        ]

    @staticmethod
    def scene_count_for(target_minutes: int) -> int:
        return min(12, max(4, math.ceil(target_minutes * 2)))
