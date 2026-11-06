import base64
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from schemas.ai_schemas import CharacterBible, ScenePlan, StoryBibleData
from services.ai.providers.base import AIProviderConfigurationError
from services.ai.providers.openai_provider import OpenAIProvider


def test_openai_provider_validates_text_outputs_and_saves_generated_images(tmp_path):
    story = {
        "title": "The Quiet Current",
        "summary": "An explorer finds a hidden ocean city.",
        "genre": "Adventure",
        "target_audience": "General audience",
        "three_act_structure": {
            "act_one": "The discovery.",
            "act_two": "The journey.",
            "act_three": "The choice.",
        },
        "main_characters": [
            {"name": "Mara", "role": "Explorer", "premise": "A curious diver."}
        ],
    }
    characters = {
        "characters": [{
            "name": "Mara",
            "role": "Explorer",
            "personality": "Curious",
            "appearance": "Blue expedition suit",
            "motivations": "Find the city",
            "relationships": "A trusted crew",
            "portrait_prompt": "Cinematic portrait of Mara",
        }]
    }
    scenes = {
        "scenes": [{
            "scene_number": 1,
            "scene_title": "The Signal",
            "scene_description": "A signal appears on the sonar.",
            "visual_description": "A diver studies a luminous display.",
            "image_prompt": "Storyboard frame, blue ocean light.",
            "estimated_duration": 35,
        }]
    }
    image = b"test-image-bytes"
    text_outputs = iter([story, characters, scenes])
    image_outputs = iter([image, image])

    def parse(**parameters):
        response_schema = parameters["response_format"]
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(
                    parsed=response_schema.model_validate(next(text_outputs)),
                    refusal=None,
                )
            )]
        )

    def generate(**_):
        return SimpleNamespace(data=[
            SimpleNamespace(b64_json=base64.b64encode(next(image_outputs)).decode("ascii"))
        ])

    provider = OpenAIProvider("test-key", "gpt-5-test", "gpt-image-test")
    provider.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(parse=parse)),
        images=SimpleNamespace(generate=generate),
    )

    generated_story = provider.generate_story("A diver discovers a city.", 3)
    generated_characters = provider.generate_character_bible(generated_story)
    generated_scenes = provider.generate_scene_plan(generated_story, generated_characters, 3)
    portrait_path = provider.generate_character_portrait(
        "Cinematic portrait", tmp_path / "portraits" / "mara.png"
    )
    scene_path = provider.generate_scene_image(
        "Storyboard frame", tmp_path / "scenes" / "scene-1.png"
    )

    assert isinstance(generated_story, StoryBibleData)
    assert isinstance(generated_characters, CharacterBible)
    assert isinstance(generated_scenes, ScenePlan)
    assert generated_scenes.scenes[0].estimated_duration == 35
    assert portrait_path.read_bytes() == image
    assert scene_path.read_bytes() == image


def test_openai_provider_requires_a_server_key():
    import pytest

    with pytest.raises(AIProviderConfigurationError, match="OPENAI_API_KEY"):
        OpenAIProvider("", "gpt-5", "gpt-image-1")
