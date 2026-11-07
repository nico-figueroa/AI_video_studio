import base64
import sys
import pytest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from schemas.ai_schemas import CharacterBible, ScenePlan, StoryBibleData
from services.ai.providers.base import AIProviderConfigurationError, AIProviderError
from services.ai.providers.openai_provider import OpenAIProvider


@pytest.mark.parametrize("reference", [False, True])
def test_image_prompt_limit_includes_reference_instructions(tmp_path, reference):
    provider = OpenAIProvider("test-key", "text-test", "image-test")
    calls = []

    def generate(**parameters):
        calls.append(parameters)
        assert len(parameters["prompt"]) == 32000
        return SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(b"image").decode())])

    provider.client = SimpleNamespace(images=SimpleNamespace(generate=generate, edit=generate))
    image = tmp_path / "reference.png"
    image.write_bytes(b"reference")
    references = [image] if reference else []
    suffix = len(provider.reference_instructions) if reference else 0
    text = "x" * (32000 - suffix)
    output = tmp_path / "output.png"
    provider.generate_consistent_image(text, output, references)
    assert output.read_bytes() == b"image"
    assert len(calls) == 1
    with pytest.raises(AIProviderError, match="no image request was sent"):
        provider.generate_consistent_image(text + "x", output, references)
    with pytest.raises(AIProviderError, match="no image request was sent"):
        provider.generate_consistent_image("x" * 36112, output, references)
    assert len(calls) == 1


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


def test_openai_provider_wraps_structured_output_validation_errors():
    import pytest

    from services.ai.providers.base import AIProviderError

    provider = OpenAIProvider("test-key", "gpt-5-test", "gpt-image-test")

    def parse(**_):
        StoryBibleData.model_validate({
            "title": "",
            "summary": "A story",
            "genre": "Adventure",
            "target_audience": "Everyone",
            "three_act_structure": {
                "act_one": "One",
                "act_two": "Two",
                "act_three": "Three",
            },
            "main_characters": [],
        })

    provider.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(parse=parse))
    )
    with pytest.raises(AIProviderError, match="text generation failed"):
        provider.generate_story("A story idea.", 1)


def test_story_bible_schema_enforces_persistence_field_limits():
    import pytest
    from pydantic import ValidationError

    valid_story = {
        "title": "A story",
        "summary": "A story summary.",
        "genre": "Adventure",
        "target_audience": "Everyone",
        "three_act_structure": {
            "act_one": "One",
            "act_two": "Two",
            "act_three": "Three",
        },
        "main_characters": [],
    }
    StoryBibleData.model_validate(valid_story)
    for field, value in (
        ("genre", "g" * 121),
        ("target_audience", "a" * 241),
        ("summary", "s" * 6001),
    ):
        with pytest.raises(ValidationError):
            StoryBibleData.model_validate({**valid_story, field: value})


def test_openai_provider_narration_and_wav_speech(tmp_path, monkeypatch):
    from contextlib import contextmanager

    calls = []

    def parse(**parameters):
        calls.append(parameters)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            parsed=parameters["response_format"](text="The explorer discovers a hidden city."),
            refusal=None,
        ))])

    @contextmanager
    def create(**parameters):
        calls.append(parameters)
        yield SimpleNamespace(stream_to_file=lambda path: path.write_bytes(b"RIFF-test-provider-response"))

    monkeypatch.setenv("OPENAI_SPEECH_MODEL", "tts-test-model")
    monkeypatch.setenv("OPENAI_SPEECH_VOICE", "alloy")
    provider = OpenAIProvider("test-key", "text-test", "image-test")
    provider.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(parse=parse)),
        audio=SimpleNamespace(speech=SimpleNamespace(with_streaming_response=SimpleNamespace(create=create))),
    )
    narration = provider.generate_narration("Discovery", "A diver finds a city.", 10)
    assert narration == "The explorer discovers a hidden city."
    output = provider.generate_speech(narration, tmp_path / "speech" / "scene.wav")
    assert output.read_bytes().startswith(b"RIFF")
    assert calls[1] == {
        "model": "tts-test-model", "voice": "alloy",
        "input": narration, "response_format": "wav",
    }


def test_reference_image_and_transcription_contracts_stay_inside_provider(tmp_path,monkeypatch):
    import pytest
    from services.ai.providers.base import AIProviderError

    reference=tmp_path/"approved.png"
    reference.write_bytes(b"approved-reference")
    handles=[]
    calls=[]
    def edit(**parameters):
        calls.append(parameters)
        handles.extend(parameters["image"])
        assert parameters["image"][0].read()==b"approved-reference"
        assert "approved references for character identity" in parameters["prompt"]
        return SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(b"generated-image").decode())])
    def transcribe(**parameters):
        calls.append(parameters)
        assert parameters["file"].read()==b"original-audio"
        return "Mira follows the map."
    provider=OpenAIProvider("test-key","text-test","image-test")
    provider.client=SimpleNamespace(images=SimpleNamespace(edit=edit),audio=SimpleNamespace(transcriptions=SimpleNamespace(create=transcribe)))
    output=provider.generate_consistent_image("Keep the silver coat",tmp_path/"new.png",[reference])
    assert output.read_bytes()==b"generated-image" and all(handle.closed for handle in handles)
    audio=tmp_path/"source.wav"
    audio.write_bytes(b"original-audio")
    monkeypatch.setenv("OPENAI_TRANSCRIPTION_MODEL","transcribe-test")
    assert provider.transcribe_audio(audio)=="Mira follows the map."
    assert calls[-1]["model"]=="transcribe-test" and calls[-1]["file"].closed
    provider.client.audio.transcriptions.create=lambda **parameters:""
    with pytest.raises(AIProviderError,match="empty transcript"):
        provider.transcribe_audio(audio)


def test_openai_provider_composes_one_structured_whole_story_arc():
    from schemas.quality import NarrativeArc

    calls=[]
    context={"story":{"previous_events":["The map was found."]},"scenes":[{"scene_id":1},{"scene_id":2}]}
    def parse(**parameters):
        calls.append(parameters)
        assert parameters["response_format"] is NarrativeArc
        assert "The map was found." in parameters["messages"][1]["content"]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            parsed=NarrativeArc.model_validate({
                "opening":"Discovery","development":"Journey","resolution":"Return",
                "scenes":[{"scene_id":1,"text":"Mira finds the map.","bridge":""},
                          {"scene_id":2,"text":"She returns to the city.","bridge":"Following its clues,"}],
            }),refusal=None,
        ))])
    provider=OpenAIProvider("test-key","text-test","image-test")
    provider.client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=parse)))
    arc=provider.compose_narration(context)
    assert len(calls)==1 and [scene.scene_id for scene in arc.scenes]==[1,2]
