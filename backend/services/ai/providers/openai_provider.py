import base64
import binascii
import json
import os
from contextlib import ExitStack
from pathlib import Path
from typing import TypeVar

from openai import OpenAI, OpenAIError
from openai.types import ImagesResponse
from pydantic import BaseModel, Field

from schemas.ai_schemas import CharacterBible, NarrativeScenePlan, ScenePlan, StoryBibleData
from schemas.quality import NarrativeArc, TimedTranscript, TranscriptWord
from services.ai.providers.base import (
    AIProvider,
    AIProviderConfigurationError,
    AIProviderError,
)


T = TypeVar("T", bound=BaseModel)


class NarrationText(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class OpenAIProvider(AIProvider):
    image_prompt_limit = 32_000
    reference_instructions = (
        "\nUse the supplied approved references for character identity. Create a new composition, not a collage."
    )

    @classmethod
    def _validate_image_prompt(cls, prompt: str) -> None:
        if len(prompt) > cls.image_prompt_limit:
            raise AIProviderError(
                f"OpenAI image prompt exceeds {cls.image_prompt_limit} characters ({len(prompt)}). "
                "Shorten the image prompt/context before retrying; no image request was sent."
            )

    def __init__(self, api_key: str, model: str, image_model: str):
        if not api_key:
            raise AIProviderConfigurationError("OPENAI_API_KEY is not configured.")
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.image_model = image_model

    def compose_narration(self, context: dict) -> NarrativeArc:
        return self._generate_json(
            "Compose ONE coherent spoken story across the ordered scenes. Plan an opening, "
            "development and resolution. Preserve character identities, prior events and locations. "
            "Each scene text continues the previous scene, not a standalone summary. Supply a short "
            "bridge spoken BEFORE each scene (empty for the first), connecting prior events to the "
            "current event and anticipating upcoming stakes without spoilers. Avoid repeating "
            "introductions, generic filler and excessive dramatic pauses. Respect scene word limits. "
            "Return every scene_id exactly once, in order.",
            json.dumps(context, ensure_ascii=True), NarrativeArc,
        )

    def transcribe_audio(self, path: Path) -> str:
        try:
            with path.open("rb") as audio:
                result = self.client.audio.transcriptions.create(
                    model=os.getenv("OPENAI_TRANSCRIPTION_MODEL", "whisper-1"),
                    file=audio, response_format="text",
                )
        except OpenAIError as error:
            raise AIProviderError(f"OpenAI transcription failed: {error}") from error
        if not isinstance(result, str) or not result.strip():
            raise AIProviderError("The provider returned an empty transcript.")
        return result.strip()

    def transcribe_audio_timed(self, path: Path) -> TimedTranscript:
        model = os.getenv("OPENAI_TRANSCRIPTION_MODEL", "whisper-1")
        if model != "whisper-1":
            raise AIProviderConfigurationError(
                "Timestamp alignment currently requires OPENAI_TRANSCRIPTION_MODEL=whisper-1."
            )
        try:
            with path.open("rb") as audio:
                result = self.client.audio.transcriptions.create(
                    model=model, file=audio, response_format="verbose_json",
                    timestamp_granularities=["word"],
                )
            return TimedTranscript(
                text=result.text,
                words=[TranscriptWord(word=word.word, start=word.start, end=word.end)
                       for word in result.words or []],
            )
        except (OpenAIError, ValueError, AttributeError) as error:
            raise AIProviderError(f"OpenAI timestamp transcription failed: {error}") from error

    def generate_consistent_image(self, prompt: str, output_path: Path, references: list[Path]) -> Path:
        if not references:
            return self._generate_image(prompt, output_path)
        request_prompt = prompt + self.reference_instructions
        self._validate_image_prompt(request_prompt)
        try:
            with ExitStack() as stack:
                images = [stack.enter_context(path.open("rb")) for path in references[:6]]
                response = self.client.images.edit(
                    model=self.image_model, image=images,
                    prompt=request_prompt,
                )
        except OpenAIError as error:
            raise AIProviderError(f"OpenAI reference image generation failed: {error}") from error
        return self._save_image_response(response, output_path)

    def generate_narration(self, title: str, description: str, seconds: int) -> str:
        return self._generate_json(
            "Write original spoken narration for this approved storyboard scene, not stage directions. "
            "Preserve the supplied story facts. Use at most the supplied maximum word count.",
            json.dumps({
                "title": title, "description": description,
                "maximum_words": min(600, max(5, int(seconds * 2.2))),
            }),
            NarrationText,
        ).text

    def generate_speech(self, text: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.client.audio.speech.with_streaming_response.create(
                model=os.getenv("OPENAI_SPEECH_MODEL", "gpt-4o-mini-tts"),
                voice=os.getenv("OPENAI_SPEECH_VOICE", "alloy"),
                input=text,
                response_format="wav",
            ) as response:
                response.stream_to_file(output_path)
        except OpenAIError as error:
            output_path.unlink(missing_ok=True)
            raise AIProviderError(f"OpenAI speech generation failed: {error}") from error
        return output_path

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

    def generate_story(self, prompt: str, target_minutes: float) -> StoryBibleData:
        return self._generate_json(
            "Create a concise, original story bible. Return JSON matching the requested fields. "
            "Include a coherent three-act structure and 2-6 named main-character seeds.",
            json.dumps({"idea": prompt, "target_seconds": round(target_minutes * 60)}),
            StoryBibleData,
        )

    def generate_character_bible(self, story: StoryBibleData) -> CharacterBible:
        return self._generate_json(
            "Develop every supplied main-character seed into a complete character bible. "
            "Preserve each name and return JSON with a characters array. If seeds are absent, extract "
            "the existing characters from the supplied story; do not invent contradictory replacements. "
            "Specify appearance, clothing, age, facial_features, distinctive_traits, portrait_prompt and negative_prompt "
            "so later artwork can retain the same identity.",
            story.model_dump_json(),
            CharacterBible,
        )

    def generate_scene_plan(
        self,
        story: StoryBibleData,
        characters: CharacterBible,
        target_minutes: float,
    ) -> ScenePlan:
        return self._generate_json(
            "Create a chronological scene plan for the supplied story. Return JSON with a scenes "
            "array. Include scene number, title, story description, visual description, image prompt, "
            "and estimated duration in seconds. Use 4-12 scenes. Allocate durations to the requested "
            "target_seconds; keep narration concise enough to fit. Do not round the target to minutes.",
            json.dumps({
                "story": story.model_dump(mode="json"),
                "characters": characters.model_dump(mode="json"),
                "target_seconds": round(target_minutes * 60),
            }),
            ScenePlan,
        )

    def generate_narrative_plan(self, story: StoryBibleData, characters: CharacterBible,
                                target_minutes: float) -> NarrativeScenePlan:
        return self._generate_json(
            "Analyze the supplied story into 2-6 chronological narrative beats, not isolated summaries. "
            "Identify each beat's purpose, timeline progression, character introductions and transition. "
            "Develop each beat into 2-4 sequential scenes (at most 12 scenes TOTAL), each with a distinct "
            "action, causal connection, consistent character appearance, geography and props. "
            "Use the full supplied story, retain its events and ending, never replace it. "
            "Camera ideas may include slow push, tracking, pan, zoom, dolly and follow movement, "
            "but do not promise that the local video model can obey these instructions. "
            "Allocate scene durations to target_seconds, not whole minutes; keep the story concise enough to fit.",
            json.dumps({"story": story.model_dump(), "characters": characters.model_dump(),
                        "target_seconds": round(target_minutes * 60)}), NarrativeScenePlan,
        )

    def generate_character_portrait(self, prompt: str, output_path: Path) -> Path:
        return self._generate_image(prompt, output_path)

    def generate_scene_image(self, prompt: str, output_path: Path) -> Path:
        return self._generate_image(prompt, output_path)

    def _generate_image(self, prompt: str, output_path: Path) -> Path:
        self._validate_image_prompt(prompt)
        try:
            response = self.client.images.generate(model=self.image_model, prompt=prompt)
        except OpenAIError as error:
            raise AIProviderError(f"OpenAI image generation failed: {error}") from error
        return self._save_image_response(response, output_path)

    @staticmethod
    def _save_image_response(response: ImagesResponse, output_path: Path) -> Path:
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
