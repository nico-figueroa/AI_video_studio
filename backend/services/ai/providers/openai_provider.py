import base64
import binascii
import json
from pathlib import Path
from typing import TypeVar

from openai import OpenAI, OpenAIError
from pydantic import BaseModel

from schemas.ai_schemas import CharacterBible, ScenePlan, StoryBibleData
from services.ai.providers.base import (
    AIProvider,
    AIProviderConfigurationError,
    AIProviderError,
)


T = TypeVar("T", bound=BaseModel)


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str, image_model: str):
        if not api_key:
            raise AIProviderConfigurationError("OPENAI_API_KEY is not configured.")
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.image_model = image_model

    def _generate_json(self, instructions: str, context: str, schema: type[T]) -> T:
        try:
            response = self.client.chat.completions.parse(
                model=self.model,
                response_format=schema,
                messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": context},
                ],
            )
        except (OpenAIError, ValueError) as error:
            raise AIProviderError(f"OpenAI text generation failed: {error}") from error

        message = response.choices[0].message
        if message.refusal:
            raise AIProviderError(f"The provider declined to generate {schema.__name__}.")
        if not isinstance(message.parsed, schema):
            raise AIProviderError(
                f"The provider returned no valid structured {schema.__name__} response."
            )
        return message.parsed

    def generate_story(self, prompt: str, target_minutes: int) -> StoryBibleData:
        return self._generate_json(
            "Create a concise, original story bible. Return JSON matching the requested fields. "
            "Include a coherent three-act structure and 2-6 named main-character seeds.",
            json.dumps({"idea": prompt, "target_minutes": target_minutes}),
            StoryBibleData,
        )

    def generate_character_bible(self, story: StoryBibleData) -> CharacterBible:
        return self._generate_json(
            "Develop every supplied main-character seed into a complete character bible. "
            "Preserve each name and return JSON with a characters array.",
            story.model_dump_json(),
            CharacterBible,
        )

    def generate_scene_plan(
        self,
        story: StoryBibleData,
        characters: CharacterBible,
        target_minutes: int,
    ) -> ScenePlan:
        return self._generate_json(
            "Create a chronological scene plan for the supplied story. Return JSON with a scenes "
            "array. Include scene number, title, story description, visual description, image prompt, "
            "and estimated duration in seconds. Use 4-12 scenes.",
            json.dumps({
                "story": story.model_dump(mode="json"),
                "characters": characters.model_dump(mode="json"),
                "target_minutes": target_minutes,
            }),
            ScenePlan,
        )

    def generate_character_portrait(self, prompt: str, output_path: Path) -> Path:
        return self._generate_image(prompt, output_path)

    def generate_scene_image(self, prompt: str, output_path: Path) -> Path:
        return self._generate_image(prompt, output_path)

    def _generate_image(self, prompt: str, output_path: Path) -> Path:
        try:
            response = self.client.images.generate(model=self.image_model, prompt=prompt)
        except OpenAIError as error:
            raise AIProviderError(f"OpenAI image generation failed: {error}") from error
        image_data = response.data[0].b64_json if response.data else None
        if not image_data:
            raise AIProviderError("The provider returned no image data.")
        try:
            image = base64.b64decode(image_data, validate=True)
        except (binascii.Error, ValueError) as error:
            raise AIProviderError("The provider returned invalid image data.") from error
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image)
        return output_path
