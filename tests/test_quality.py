import base64
import io
import json
import math
from pathlib import Path
import struct
import subprocess
import wave

from PIL import Image
import pytest

from test_api import FixtureAIProvider, client
from test_production import production, approve, prepare_audio
from models.models import Project
from schemas.quality import NarrativeArc, NarrationScene, MotionPlan
from services.video_composer_service import VideoComposerService
from services.image_asset_service import ImageAssetService
from services.ai.providers.base import AIProviderError


def test_image_context_budget_preserves_composition_identity_and_valid_json(caplog):
    text = "Full scene composition: Mira opens the vault; retain the engraved red key. " * 40
    context = {"characters": [
        {"id": index, "name": f"Character {index}", "appearance": "银色外套 green eyes " * 1000,
         "facial_features": "Distinctive freckles " * 500, "clothing": "silver coat " * 500,
         "negative_prompt": "no different face " * 500, "age": "44", "role": "Explorer"}
        for index in range(12)
    ], "prompt_package_policy": "Preserve approved references."}
    story = {
        "story_bible": "The journey continues. " * 1000,
        "character_bible": context["characters"],
        "scene_history": [{"event": "Repeated event " * 1000}],
        "previous_events": ["Prior event " * 1000 for _ in range(12)],
        "upcoming_events": ["Upcoming event " * 1000 for _ in range(12)],
        "scene_bridge": {"previous": {"title": "The gate", "location_objects_and_visuals": "red key"},
                        "current": {"title": "The vault"}, "next": {"title": "Return"}},
        "timeline": list(range(12)),
    }
    prompt = ImageAssetService.image_prompt(text, context, story)
    assert prompt.startswith(text)
    assert len(prompt) <= 30000
    character_json, story_json = prompt.split("STORY CONTINUITY:\n")
    identity = json.loads(character_json.split("unchanged):\n")[1])
    continuity = json.loads(story_json)
    assert [item["name"] for item in identity["characters"]] == [f"Character {index}" for index in range(12)]
    assert all(item["age"] == "44" and "green eyes" in item["appearance"] for item in identity["characters"])
    assert continuity["scene_bridge"] == story["scene_bridge"]
    assert len(continuity["previous_events"]) == len(continuity["upcoming_events"]) == 12
    assert continuity["timeline"] == story["timeline"]
    assert "character_bible" not in continuity and "scene_history" not in continuity
    assert "context excerpted" in caplog.text
    assert story["story_bible"].endswith("continues. ")
    with pytest.raises(AIProviderError, match="no image request was sent"):
        ImageAssetService.image_prompt("x" * 32000, context, story)


def create(http):
    return http.post("/api/v1/projects",json={"prompt":"A diver follows a luminous map beneath the ocean.","max_budget":20}).json()["project_id"]


def supplied_character():
    return dict(name="Mira",role="Explorer",appearance="Silver coat, green eyes",personality="Curious",
                motivations="Find the city",relationships="Trusts the guide",portrait_prompt="Mira in her silver coat")


def png():
    content = io.BytesIO()
    Image.new("RGB",(80,60),(30,80,140)).save(content,format="PNG")
    return base64.b64encode(content.getvalue()).decode()


def wav(frequency=None):
    content = io.BytesIO()
    with wave.open(content,"wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(
            b"".join(struct.pack("<h",int(12000*math.sin(index*2*math.pi*frequency/16000))) for index in range(16000))
            if frequency else b"\0\0"*16000
        )
    return base64.b64encode(content.getvalue()).decode()


@pytest.mark.parametrize(("payload","kind"),[
    ({"text":"An explorer follows a hidden map."},"text_story"),
    ({"text":"Scene 1: Arrival\n\nScene 2: Discovery"},"scene_descriptions"),
    ({"text":"Narrator: The journey begins."},"narration_script"),
    ({"text":"Character: Mira\nSilver coat and green eyes."},"character_definitions"),
    ({"audio":{"name":"voice.wav","content_base64":"YQ=="}},"audio_file"),
    ({"images":[{"name":"frame.png","content_base64":"YQ==","description":"An ocean city"}]},"image_collection"),
    ({"text":"A story","characters":[supplied_character()]},"mixed_inputs"),
])
def test_classification_is_local_and_correctable(client,payload,kind):
    http,_,_ = client
    response = http.post("/api/v1/inputs/classify",json=payload)
    assert response.status_code==200,response.text
    assert kind in response.json()["kinds"]
    corrected = http.post("/api/v1/inputs/classify",json={"text":"Scene 1: This is actually a spoken script.","text_kind":"narration_script"})
    assert corrected.json()["kinds"]==["narration_script"]


def test_review_guard_cancel_stale_token_and_explicit_override(client):
    http, sessions,_ = client
    project_id=create(http)
    http.post(f"/api/v1/projects/{project_id}/analyze")
    character=http.get(f"/api/v1/projects/{project_id}/characters").json()[0]
    path=f"/api/v1/characters/{character['id']}/portrait"
    spend=http.get(f"/api/v1/projects/{project_id}").json()["estimated_spend"]
    blocked=http.post(path)
    assert blocked.status_code==409
    warning=blocked.json()["detail"]
    assert warning["stage"]=="story" and warning["consequences"] and warning["required_action"]
    assert http.get(f"/api/v1/projects/{project_id}").json()["estimated_spend"]==spend
    # Cancelling means no retry and no spend. A token must also match the latest content.
    story=http.get(f"/api/v1/projects/{project_id}/story").json()
    story["summary"]+=" A new event."
    assert http.put(f"/api/v1/projects/{project_id}/story",json=story).status_code==200
    assert http.post(path,headers={"X-Workflow-Override":warning["confirmation_token"]}).status_code==409
    current=http.post(path).json()["detail"]
    assert http.post(path,headers={"X-Workflow-Override":current["confirmation_token"]}).status_code==200
    with sessions() as db:
        project=db.get(Project,project_id)
        assert not project.story_approved
        assert len(project.review_overrides)==1
        assert project.review_overrides[0]["stage"]=="story"


def test_story_revision_and_reference_memory_condition_every_image(client,monkeypatch):
    http,sessions,_=client
    project_id=create(http)
    http.post(f"/api/v1/projects/{project_id}/analyze")
    quality=http.get(f"/api/v1/projects/{project_id}/quality").json()
    path=f"/api/v1/projects/{project_id}/story/approval"
    assert http.post(path,json={"approved":True,"revision":"0"*64}).status_code==409
    assert http.post(path,json={"approved":True,"revision":quality["story_revision"]}).status_code==200
    calls=[]
    original=FixtureAIProvider.generate_consistent_image
    def generate(self,prompt,output,references):
        calls.append((prompt,list(references)))
        return original(self,prompt,output,references)
    monkeypatch.setattr(FixtureAIProvider,"generate_consistent_image",generate)
    for character in http.get(f"/api/v1/projects/{project_id}/characters").json():
        assert http.post(f"/api/v1/characters/{character['id']}/portrait").status_code==200
        current=next(item for item in http.get(f"/api/v1/projects/{project_id}/characters").json() if item["id"]==character["id"])
        assert http.put(f"/api/v1/characters/{character['id']}",json={"approved":True,"expected_image_path":current["image_path"]}).status_code==200
    assert len(calls[-1][1])==2
    scene=http.get(f"/api/v1/projects/{project_id}/scenes").json()[0]
    assert http.post(f"/api/v1/scenes/{scene['id']}/generate").status_code==200
    prompt,references=calls[-1]
    assert len(references)==3 and all(path.is_file() for path in references)
    assert "CHARACTER MEMORY" in prompt and "STORY CONTINUITY" in prompt
    assert "previous_events" in prompt and "upcoming_events" in prompt
    quality=http.get(f"/api/v1/projects/{project_id}/quality").json()
    assert "not visual identity" in quality["explanation"]
    assert quality["dimensions"]["scene_continuity"]==25
    with sessions() as db:
        assert all(item.reference_image_paths for item in db.get(Project,project_id).characters)


def test_connected_arc_bridges_reordering_and_bad_provider_output(production,monkeypatch):
    http,_,_,project_id,provider=production
    prepare_audio(production)
    narration=http.get(f"/api/v1/projects/{project_id}/narration").json()
    assert provider.text_calls==1
    assert narration["items"][1]["transition_text"] in narration["items"][1]["text"]
    assert narration["items"][1]["text"].count(narration["items"][1]["transition_text"])==1
    timeline=http.get(f"/api/v1/projects/{project_id}/timeline").json()
    timeline["scenes"].reverse()
    assert http.put(f"/api/v1/projects/{project_id}/timeline",json=timeline).status_code==200
    assert all(item["stale"] for item in http.get(f"/api/v1/projects/{project_id}/narration").json()["items"])
    def broken(context):
        return NarrativeArc(opening="Start",development="Middle",resolution="End",scenes=[
            NarrationScene(scene_id=context["scenes"][0]["scene_id"],text="Wrong incomplete arc",bridge="")
        ])
    monkeypatch.setattr(provider,"compose_narration",broken)
    assert approve(http,project_id,regenerate=True).status_code==502
    assert http.get(f"/api/v1/projects/{project_id}/narration").json()["items"]==[
        {**item,"stale":True} for item in narration["items"]
    ]


def test_import_preserves_story_characters_images_and_generates_nothing(client,monkeypatch):
    http,sessions,storage=client
    project_id=create(http)
    story="\n Mira stepped into the sea.\n\nShe returned with a map. Every supplied word stays. \n"
    payload={
        "title":"Mira's map","text":story,"text_kind":"text_story","characters":[supplied_character()],
        "scenes":[{"title":"Map","description":"Mira returns with a map.","duration_seconds":3}],
        "images":[{"name":"../../not-a-path.png","content_base64":png(),"description":"Mira with a map"}],
    }
    response=http.post(f"/api/v1/projects/{project_id}/inputs",json=payload)
    assert response.status_code==200,response.text
    assert "mixed_inputs" in response.json()["classification"]["kinds"]
    estimate=http.get(f"/api/v1/projects/{project_id}/generation-estimates").json()["planning"]
    assert estimate["estimated_api_calls"]==0 and estimate["estimated_cost"]==0
    def forbidden(*args,**kwargs):
        raise AssertionError("Supplied content must not cause provider calls or construction.")
    monkeypatch.setattr("services.project_service.create_ai_provider",forbidden)
    assert http.post(f"/api/v1/projects/{project_id}/analyze").status_code==200
    saved=http.get(f"/api/v1/projects/{project_id}/story").json()
    assert saved["summary"]==story and saved["characters"][0]["name"]=="Mira"
    assert saved["scenes"][0]["description"]==payload["scenes"][0]["description"]
    assert http.get(saved["scenes"][0]["image_path"]).status_code==200
    assert saved["scenes"][0]["motion_plan"]["execution"]=="camera_effects_only"
    assert not (storage/"not-a-path.png").exists()
    with sessions() as db:
        assert db.get(Project,project_id).estimated_spend==0
    assert http.post(f"/api/v1/projects/{project_id}/inputs",json=payload).status_code==409


def test_audio_transcription_approval_missing_only_planning_and_original_audio(client,monkeypatch):
    http,sessions,_=client
    project_id=create(http)
    calls=[]
    class InputProvider(FixtureAIProvider):
        def transcribe_audio_timed(self,path):
            from schemas.quality import TimedTranscript, TranscriptWord
            calls.append("transcribe")
            assert path.is_file()
            text = "Mira enters the water and discovers a luminous city."
            return TimedTranscript(text=text, words=[
                TranscriptWord(word=word, start=index/10, end=(index+1)/10)
                for index,word in enumerate(text.split())
            ])
        def generate_story(self,prompt,target_minutes):
            calls.append("story")
            return super().generate_story(prompt,target_minutes)
        def generate_character_bible(self,*args):
            raise AssertionError("Do not replace supplied characters.")
        def generate_scene_plan(self,*args):
            raise AssertionError("Preserve supplied narration as a single segment.")
    provider=InputProvider()
    monkeypatch.setattr("services.input_analysis_service.create_ai_provider",lambda config:provider)
    monkeypatch.setattr("services.project_service.create_ai_provider",lambda config:provider)
    payload={"audio":{"name":"narration.wav","content_base64":wav()},"characters":[supplied_character()]}
    response=http.post(f"/api/v1/projects/{project_id}/inputs",json=payload)
    assert response.status_code==200,response.text
    assert calls==[]
    assert http.post(f"/api/v1/projects/{project_id}/analyze").status_code==409
    estimate=http.get(f"/api/v1/projects/{project_id}/inputs/transcription-estimate").json()
    assert http.post(f"/api/v1/projects/{project_id}/inputs/transcribe",json={"approved":False,"estimate_id":estimate["estimate_id"]}).status_code==422
    assert calls==[]
    assert http.post(f"/api/v1/projects/{project_id}/inputs/transcribe",json={"approved":True,"estimate_id":estimate["estimate_id"]}).status_code==200
    planning=http.get(f"/api/v1/projects/{project_id}/generation-estimates").json()["planning"]
    assert planning["estimated_api_calls"]==1
    assert http.post(f"/api/v1/projects/{project_id}/analyze").status_code==200
    assert calls==["transcribe","story"]
    narration=http.get(f"/api/v1/projects/{project_id}/narration").json()
    assert len(narration["items"])==1 and not narration["items"][0]["stale"]
    assert narration["items"][0]["text"]=="Mira enters the water and discovers a luminous city."
    assert narration["items"][0]["audio_seconds"]==pytest.approx(1)
    assert http.get(narration["items"][0]["audio_url"]).content[:4]==b"RIFF"
    assert narration["audio_estimate"]["estimated_api_calls"]==0
    with sessions() as db:
        manifest=db.get(Project,project_id).input_manifest
        assert Path(manifest["source_audio"]).is_file()
        assert Path(manifest["original_audio"]).read_bytes()==base64.b64decode(payload["audio"]["content_base64"])
    from test_api import confirmed_post
    scene=http.get(f"/api/v1/projects/{project_id}/scenes").json()[0]
    assert confirmed_post(http,f"/api/v1/scenes/{scene['id']}/generate").status_code==200
    scene=http.get(f"/api/v1/projects/{project_id}/scenes").json()[0]
    assert http.put(f"/api/v1/scenes/{scene['id']}",json={"approved":True,"expected_image_path":scene["image_path"]}).status_code==200
    with sessions() as db:
        audio=Path(db.get(Project,project_id).scenes[0].narration.audio_path)
        original=audio.read_bytes()
        audio.unlink()
    def forbidden(*args,**kwargs):
        raise AssertionError("Missing original audio must be restored locally, not synthesized.")
    monkeypatch.setattr("services.narration_service.create_ai_provider",forbidden)
    estimate=http.get(f"/api/v1/projects/{project_id}/narration").json()["audio_estimate"]
    assert estimate["estimated_cost"]==0 and estimate["estimated_api_calls"]==0 and estimate["estimated_runtime_seconds"]>0
    restored=http.post(f"/api/v1/projects/{project_id}/narration/audio",json={"approved":True,"estimate_id":estimate["estimate_id"]})
    assert restored.status_code==200,restored.text
    assert http.get(restored.json()["items"][0]["audio_url"]).content==original


@pytest.mark.parametrize("file",[
    {"name":"image.png","content_base64":"!!!!","description":"A city"},
    {"name":"image.png","content_base64":base64.b64encode(b"not an image").decode(),"description":"A city"},
    {"name":"image.png","content_base64":png(),"description":""},
])
def test_invalid_upload_is_visible_and_transactional(client,file):
    http,sessions,_=client
    project_id=create(http)
    response=http.post(f"/api/v1/projects/{project_id}/inputs",json={"images":[file]})
    assert response.status_code==422
    with sessions() as db:
        project=db.get(Project,project_id)
        assert project.scenes==[] and project.input_manifest=={}


def test_supplied_script_restores_locally_after_reordering(client,monkeypatch):
    http,sessions,_=client
    project_id=create(http)
    script="Mira enters the water. She discovers the city and returns with the map."
    payload={
        "text":script,"text_kind":"narration_script","characters":[supplied_character()],
        "scenes":[{"title":"Arrival","description":"Mira enters the water."},{"title":"Return","description":"She returns with the map."}],
        "images":[{"name":f"{index}.png","content_base64":png(),"description":"Mira at sea"} for index in range(2)],
    }
    assert http.post(f"/api/v1/projects/{project_id}/inputs",json=payload).status_code==200
    assert http.post(f"/api/v1/projects/{project_id}/analyze").status_code==200
    scenes=http.get(f"/api/v1/projects/{project_id}/scenes").json()
    for scene in scenes:
        assert http.put(f"/api/v1/scenes/{scene['id']}",json={"approved":True,"expected_image_path":scene["image_path"]}).status_code==200
    timeline=http.get(f"/api/v1/projects/{project_id}/timeline").json()
    timeline["scenes"].reverse()
    assert http.put(f"/api/v1/projects/{project_id}/timeline",json=timeline).status_code==200
    estimate=http.get(f"/api/v1/projects/{project_id}/narration").json()["narration_estimate"]
    assert estimate["estimated_api_calls"]==0 and estimate["estimated_cost"]==0
    def forbidden(*args,**kwargs):
        raise AssertionError("Restoring supplied narration must not construct a paid provider.")
    monkeypatch.setattr("services.narration_service.create_ai_provider",forbidden)
    restored=http.post(f"/api/v1/projects/{project_id}/narration",json={"approved":True,"estimate_id":estimate["estimate_id"],"regenerate":True})
    assert restored.status_code==200,restored.text
    assert all(not item["stale"] for item in restored.json()["items"])
    by_id={item["scene_id"]:item["text"] for item in restored.json()["items"]}
    assert " ".join(by_id[item["scene_id"]] for item in timeline["scenes"])==script


def test_scene_review_override_never_bypasses_missing_files(production):
    http,sessions,storage,project_id,provider=production
    scene=http.get(f"/api/v1/projects/{project_id}/scenes").json()[0]
    assert http.put(f"/api/v1/scenes/{scene['id']}",json={"approved":False,"expected_image_path":scene["image_path"]}).status_code==200
    estimate=http.get(f"/api/v1/projects/{project_id}/narration").json()["narration_estimate"]
    payload={"approved":True,"estimate_id":estimate["estimate_id"]}
    path=f"/api/v1/projects/{project_id}/narration"
    warning=http.post(path,json=payload)
    assert warning.status_code==409 and warning.json()["detail"]["stage"]=="scenes"
    token=warning.json()["detail"]["confirmation_token"]
    assert provider.text_calls==0
    # Delete a required image after confirmation was offered; an override must not spend.
    (storage/"projects"/str(project_id)/f"scene-{scene['id']}.png").unlink()
    spend=http.get(f"/api/v1/projects/{project_id}").json()["estimated_spend"]
    blocked=http.post(path,json=payload,headers={"X-Workflow-Override":token})
    assert blocked.status_code==409 and isinstance(blocked.json()["detail"],str)
    assert provider.text_calls==0
    assert http.get(f"/api/v1/projects/{project_id}").json()["estimated_spend"]==spend


@pytest.mark.parametrize("payload",[
    {"text":"Scene 1: Arrival\nScene 2: Return","text_kind":"scene_descriptions",
     "images":[{"name":"frame.png","content_base64":png(),"description":"A city"}]},
    {"text":"Character:\nA silver coat","text_kind":"character_definitions"},
    {"text":"x"*4001,"text_kind":"scene_descriptions"},
])
def test_invalid_derived_input_shape_returns_actionable_validation_error(client,payload):
    http,sessions,_=client
    project_id=create(http)
    response=http.post(f"/api/v1/projects/{project_id}/inputs",json=payload)
    assert response.status_code==422,response.text
    with sessions() as db:
        assert not db.get(Project,project_id).scenes


@pytest.mark.parametrize("transition",["cross_fade","fade_black","fade_color","motion_blur"])
def test_actual_transition_export_preserves_duration_and_audio(tmp_path,transition):
    composer=VideoComposerService()
    composer.width,composer.height=320,180
    sources=[]
    durations=[1,1]
    plans=[MotionPlan(camera="parallax",transition=transition),MotionPlan(camera="pan")]
    for index,color in enumerate(((210,40,30),(30,70,210))):
        image=tmp_path/f"{index}.png"
        Image.new("RGB",(400,240),color).save(image)
        audio=tmp_path/f"{index}.wav"
        audio.write_bytes(base64.b64decode(wav(440*(index+1))))
        output=tmp_path/f"{index}.mp4"
        composer.segment(image,audio,1,output,index,plan=plans[index],tail=.5 if index==0 else 0)
        sources.append(output)
    output=tmp_path/"combined.mp4"
    composer.combine(sources,output,plans,durations)
    composer.validate(output)
    probe=subprocess.run([composer.ffmpeg,"-hide_banner","-i",str(output)],stdin=subprocess.DEVNULL,capture_output=True,text=True)
    assert "Duration: 00:00:02.00" in probe.stderr
    frames=subprocess.run([composer.ffmpeg,"-v","error","-i",str(output),"-vf","scale=1:1","-f","rawvideo","-pix_fmt","rgb24","-"],
                          stdin=subprocess.DEVNULL,capture_output=True)
    assert frames.returncode==0
    assert len(frames.stdout)==48*3
    samples=[frames.stdout[index*3:index*3+3] for index in range(24,36)]
    if transition=="fade_black":
        assert min(max(pixel) for pixel in samples)<20
    elif transition=="fade_color":
        assert max(min(pixel) for pixel in samples)>235
    else:
        assert any(pixel[0]>40 and pixel[2]>40 for pixel in samples)
    audio=subprocess.run([composer.ffmpeg,"-v","error","-i",str(output),"-map","0:a","-ar","16000","-ac","1","-f","s16le","-"],
                         stdin=subprocess.DEVNULL,capture_output=True)
    assert audio.returncode==0
    samples=[item[0] for item in struct.iter_unpack("<h",audio.stdout)]
    for start,frequency in ((0.8,440),(1.8,880)):
        tail=samples[int(start*16000):int((start+.15)*16000)]
        assert math.sqrt(sum(value**2 for value in tail)/len(tail))>5000
        crossings=sum((left>=0)!=(right>=0) for left,right in zip(tail,tail[1:]))
        assert abs(crossings/(.15*2)-frequency)<25


def test_six_animated_scenes_preserve_each_visual_and_narration(tmp_path):
    composer = VideoComposerService()
    composer.width, composer.height = 160, 90
    colors = [(220, 30, 30), (30, 220, 30), (30, 30, 220),
              (220, 220, 30), (220, 30, 220), (30, 220, 220)]
    durations = [3, 1, 2, 1, 2, 1]
    sources = []
    for index, (color, duration) in enumerate(zip(colors, durations)):
        clip = tmp_path / f"clip-{index}.mp4"
        color_hex = "0x" + "".join(f"{value:02x}" for value in color)
        composer._run(["-y", "-f", "lavfi", "-i", f"color=c={color_hex}:s=160x90:r=24",
                       "-t", "0.5", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)])
        speech = tmp_path / f"speech-{index}.wav"
        speech.write_bytes(base64.b64decode(wav(440 + index * 110)))
        segment = tmp_path / f"scene-{index}.mp4"
        composer.animated_segment(clip, speech, duration, segment, tail=.5 if index < 5 else 0)
        sources.append(segment)
    output = tmp_path / "six-scenes.mp4"
    composer.combine(sources, output, [MotionPlan() for _ in sources], durations)
    offset = 0
    for color, duration in zip(colors, durations):
        frame = subprocess.run(
            [composer.ffmpeg, "-v", "error", "-ss", str(offset + .8), "-i", str(output),
             "-frames:v", "1", "-vf", "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            stdin=subprocess.DEVNULL, capture_output=True, check=True,
        ).stdout
        assert len(frame) == 3
        assert max(abs(actual - expected) for actual, expected in zip(frame, color)) < 15
        audio = subprocess.run(
            [composer.ffmpeg, "-v", "error", "-ss", str(offset + .2), "-t", "0.2", "-i", str(output),
             "-map", "0:a:0", "-ar", "16000", "-ac", "1", "-f", "s16le", "-"],
            stdin=subprocess.DEVNULL, capture_output=True, check=True,
        ).stdout
        samples = [item[0] for item in struct.iter_unpack("<h", audio)]
        assert samples and math.sqrt(sum(value**2 for value in samples) / len(samples)) > 5000
        offset += duration
    probe = subprocess.run([composer.ffmpeg, "-hide_banner", "-i", str(output)],
                           stdin=subprocess.DEVNULL, capture_output=True, text=True)
    assert "Duration: 00:00:10.00" in probe.stderr
