import base64
import io
from pathlib import Path
from types import SimpleNamespace
import wave

import pytest
from fastapi import HTTPException

from test_api import FixtureAIProvider, client
from test_production import production, prepare_audio, render_payload
from models.models import AnimationJob, Project
from schemas.ai_schemas import NarrativeScenePlan
from schemas.inputs import InputBundle
from services.ai.providers.base import AIProviderConfigurationError
from services.ai.providers.local_svd import LocalSVDProvider, require_disk_space
from services.document_input_service import DocumentInputService
from services.narrative_analysis_service import NarrativeAnalysisService
from services.video_composer_service import VideoComposerService


def payload(name, data):
    return {"name": name, "content_base64": base64.b64encode(data).decode()}


def test_local_runtime_requires_license_and_preserves_disk_reserve(monkeypatch, tmp_path):
    monkeypatch.delenv("LOCAL_ANIMATION_LICENSE_ACCEPTED", raising=False)
    with pytest.raises(AIProviderConfigurationError, match="disabled"):
        LocalSVDProvider().check_ready()
    monkeypatch.setattr("services.ai.providers.local_svd.shutil.disk_usage",
                        lambda path: SimpleNamespace(free=15 * 1024**3))
    with pytest.raises(AIProviderConfigurationError, match="15 GiB"):
        require_disk_space(tmp_path)


def test_local_provider_never_claims_directed_motion():
    quote = LocalSVDProvider().estimate_animation_cost()
    assert quote["provider_cost"] == 0
    assert "no text-directed motion" in quote["limitations"]
    with pytest.raises(RuntimeError, match="does not support directed"):
        LocalSVDProvider().generate_transition_animation()


def test_final_render_preserves_fifteen_gib_reserve(production, monkeypatch):
    http, _, _, project_id, _ = production
    prepare_audio(production)
    monkeypatch.setattr("services.render_service.shutil.disk_usage",
                        lambda path: SimpleNamespace(free=15 * 1024**3))
    response = http.post(f"/api/v1/projects/{project_id}/render", json=render_payload(http, project_id))
    assert response.status_code == 422
    assert "15 GiB" in response.json()["detail"]


def fake_animation(monkeypatch, sessions):
    import api.animation_routes
    monkeypatch.setattr(api.animation_routes, "SessionLocal", sessions)
    monkeypatch.setattr(LocalSVDProvider, "check_ready", lambda self: None)
    def generate(self, image, output, **kwargs):
        assert image.is_file()
        output.parent.mkdir(parents=True, exist_ok=True)
        VideoComposerService()._run([
            "-y", "-f", "lavfi", "-i", "testsrc2=size=128x72:rate=7",
            "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output),
        ])
        return {"frames":14, "duration_seconds":2, "model":"fixture"}
    monkeypatch.setattr(LocalSVDProvider, "generate_scene_animation", generate)


def test_approved_generated_clip_enters_real_render_and_stale_clip_blocks(production, monkeypatch):
    http, sessions, _, project_id, _ = production
    fake_animation(monkeypatch, sessions)
    prepare_audio(production)
    scenes = http.get(f"/api/v1/projects/{project_id}/scenes").json()
    scene_id = scenes[0]["id"]
    route = f"/api/v1/projects/{project_id}/scenes/{scene_id}/animation"
    state = http.get(route).json()
    assert state["job"] is None
    assert http.post(route, json={"approved":False, "estimate_id":state["estimate"]["estimate_id"]}).status_code == 422
    assert http.post(route, json={"approved":True, "estimate_id":"0"*64}).status_code == 409
    response = http.post(route, json={"approved":True, "estimate_id":state["estimate"]["estimate_id"]})
    assert response.status_code == 202, response.text
    job = http.get(route).json()["job"]
    assert job["status"] == "completed" and not job["approved"]
    assert http.get(job["clip_url"]).status_code == 200
    assert http.put(route+"/approval", json={"job_id":job["job_id"], "approved":True}).status_code == 200
    timeline = http.get(f"/api/v1/projects/{project_id}/timeline").json()
    assert timeline["scenes"][0]["animation_url"] == job["clip_url"]
    assert http.post(f"/api/v1/projects/{project_id}/render", json=render_payload(http, project_id)).status_code == 202
    assert http.get(f"/api/v1/projects/{project_id}/render/status").json()["status"] == "completed"
    assert http.get(f"/api/v1/projects/{project_id}/video/download").status_code == 200
    with sessions() as db:
        scene = db.get(Project, project_id).scenes[0]
        scene.visual_description += " New location."
        db.commit()
    timeline = http.get(f"/api/v1/projects/{project_id}/timeline").json()
    assert not timeline["ready"]
    assert "stale" in timeline["scenes"][0]["animation_issue"]
    with sessions() as db:
        Path(db.get(AnimationJob, job["job_id"]).clip_path).unlink()
    # Missing/stale selections must remain removable, not force a silent still-image fallback.
    assert http.put(route+"/approval", json={"job_id":job["job_id"], "approved":False}).status_code == 200
    assert http.get(f"/api/v1/projects/{project_id}/timeline").json()["scenes"][0]["animation_issue"] is None


def test_animation_failure_and_project_mutation_lock(production, monkeypatch):
    http, sessions, _, project_id, _ = production
    fake_animation(monkeypatch, sessions)
    monkeypatch.setattr("api.animation_routes.run_animation", lambda job_id: None)
    scenes = http.get(f"/api/v1/projects/{project_id}/scenes").json()
    def start(scene):
        route = f"/api/v1/projects/{project_id}/scenes/{scene}/animation"
        estimate = http.get(route).json()["estimate"]
        return http.post(route, json={"approved":True,"estimate_id":estimate["estimate_id"]})
    response = start(scenes[0]["id"])
    assert response.status_code == 202
    assert start(scenes[1]["id"]).status_code == 409
    assert http.put(f"/api/v1/scenes/{scenes[0]['id']}", json={
        "approved":False, "expected_image_path":scenes[0]["image_path"],
    }).status_code == 409
    from repositories.production_repository import ProductionRepository
    from services.animation_service import AnimationService
    def fail(*args, **kwargs):
        raise RuntimeError("CUDA fixture failure")
    monkeypatch.setattr(LocalSVDProvider, "generate_scene_animation", fail)
    with sessions() as db:
        AnimationService(ProductionRepository(db)).run(response.json()["job_id"])
    state = http.get(f"/api/v1/projects/{project_id}/scenes/{scenes[0]['id']}/animation").json()
    assert state["job"]["status"] == "failed"
    assert "CUDA fixture failure" in state["job"]["error"]


def test_beats_have_multiple_sequential_scenes_and_detect_oversized_plan():
    def beat(title):
        return {"title":title,"purpose":"A cause leads to a consequence.","timeline_progression":"Later",
                "character_introductions":["Mira"],"transition":"Continue to next location",
                "scenes":[{"scene_number":1,"scene_title":f"{title} {i}","scene_description":"An event",
                           "visual_description":"The same character","image_prompt":"A frame","estimated_duration":3}
                          for i in range(2)]}
    plan = NarrativeScenePlan.model_validate({"beats":[beat("Arrival"),beat("Discovery")]})
    flat = NarrativeAnalysisService.flatten(plan)
    assert [scene.scene_number for scene in flat.scenes] == [1,2,3,4]
    assert [scene.beat_number for scene in flat.scenes] == [1,1,2,2]
    with pytest.raises(ValueError):
        NarrativeScenePlan.model_validate({"beats":[{**beat("Bad"),"scenes":beat("Bad")["scenes"][:1]}]})


@pytest.mark.parametrize("name,data", [
    ("story.txt", b"Keep this exact story."),
    ("story.md", b"# A story\n\nMira finds a gate."),
    ("story.json", b'{"text":"Preserve this story."}'),
    ("story.yaml", b'text: Preserve this story.\ntext_kind: text_story'),
    ("scenes.csv", b'title,description,duration_seconds\nArrival,Mira arrives,3\n'),
    ("characters.csv", b'name,appearance\nMira,Silver coat\n'),
])
def test_document_types_are_parsed_locally_and_classified(name, data):
    parsed = DocumentInputService.expand(InputBundle(documents=[payload(name,data)]))
    assert parsed.text or parsed.scenes or parsed.characters


def test_docx_and_pdf_import_and_bad_documents():
    from docx import Document
    from pypdf import PdfWriter
    document = Document()
    document.add_paragraph("Mira follows the river.")
    buffer = io.BytesIO()
    document.save(buffer)
    parsed = DocumentInputService.expand(InputBundle(documents=[payload("story.docx", buffer.getvalue())]))
    assert parsed.text == "Mira follows the river."
    pdf = PdfWriter()
    pdf.add_blank_page(width=100,height=100)
    buffer = io.BytesIO()
    pdf.write(buffer)
    with pytest.raises(HTTPException) as failure:
        DocumentInputService.expand(InputBundle(documents=[payload("scan.pdf", buffer.getvalue())]))
    assert "OCR" in failure.value.detail
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    text_pdf = PdfWriter()
    page = text_pdf.add_blank_page(width=200, height=100)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): text_pdf._add_object(font)}),
    })
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 10 50 Td (Mira follows the river.) Tj ET")
    page[NameObject("/Contents")] = text_pdf._add_object(stream)
    buffer = io.BytesIO()
    text_pdf.write(buffer)
    parsed = DocumentInputService.expand(InputBundle(documents=[payload("story.pdf", buffer.getvalue())]))
    assert parsed.text == "Mira follows the river."
    for name,data in [("bad.json",b'{"unsupported":true}'),("bad.docx",b"not a zip"),
                      ("bad.yaml",b"x: &a [*a]"),("bad.csv",b"unknown\nvalue")]:
        with pytest.raises(HTTPException):
            DocumentInputService.expand(InputBundle(documents=[payload(name,data)]))


def test_openai_hierarchical_plan_persists_beats_and_film_bridges(client, monkeypatch):
    from services.ai.providers.openai_provider import OpenAIProvider
    http, _, _ = client
    fixture = FixtureAIProvider()
    story = fixture.generate_story("A diver discovers a city.", 1)
    characters = fixture.generate_character_bible(story)
    scenes = fixture.generate_scene_plan(story, characters, 1).scenes
    response = {"beats":[
        {"title":title,"purpose":"A cause leads to a consequence.","timeline_progression":"Later",
         "character_introductions":["The Explorer"] if index == 0 else [],"transition":"Continue",
         "scenes":[scene.model_dump() for scene in scenes[index*2:index*2+2]]}
        for index,title in enumerate(["Arrival","Discovery"])
    ]}
    calls = []
    def parse(**parameters):
        calls.append(parameters)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            parsed=parameters["response_format"].model_validate(response), refusal=None,
        ))])
    adapter = OpenAIProvider("test-key", "test-model", "test-image")
    adapter.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=parse)))
    fixture.generate_narrative_plan = adapter.generate_narrative_plan
    monkeypatch.setattr("services.project_service.create_ai_provider", lambda configuration: fixture)
    project_id = http.post("/api/v1/projects", json={"prompt":"A diver discovers a hidden city."}).json()["project_id"]
    assert http.post(f"/api/v1/projects/{project_id}/analyze").status_code == 200
    film = http.get(f"/api/v1/projects/{project_id}/film-plan").json()
    assert film["narrative"]["source"] == "provider_story_decomposition"
    assert [len(beat["scene_ids"]) for beat in film["narrative"]["beats"]] == [2,2]
    assert [scene["beat_number"] for scene in film["scenes"]] == [1,1,2,2]
    assert film["scenes"][1]["bridge"]["previous"]["scene_id"] == film["scenes"][0]["scene_id"]
    assert film["scenes"][1]["bridge"]["next"]["scene_id"] == film["scenes"][2]["scene_id"]
    assert len(calls) == 1


def test_timestamp_aligned_source_audio_uses_unequal_scene_ranges(client, monkeypatch):
    from schemas.quality import TimedTranscript, TranscriptWord
    http, _, _ = client
    class TimedProvider(FixtureAIProvider):
        def transcribe_audio_timed(self, path):
            return TimedTranscript(text="Mira arrives. Mira explores.", words=[
                TranscriptWord(word="Mira",start=0,end=.2),
                TranscriptWord(word="arrives.",start=.2,end=.5),
                TranscriptWord(word="Mira",start=.7,end=1),
                TranscriptWord(word="explores.",start=1,end=3.5),
            ])
    provider = TimedProvider()
    monkeypatch.setattr("services.input_analysis_service.create_ai_provider", lambda configuration: provider)
    monkeypatch.setattr("services.project_service.create_ai_provider", lambda configuration: provider)
    buffer = io.BytesIO()
    with wave.open(buffer,"wb") as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000)
        audio.writeframes(b"\0\0" * 64000)
    project_id = http.post("/api/v1/projects",json={"prompt":"Mira arrives and explores the river."}).json()["project_id"]
    route = f"/api/v1/projects/{project_id}"
    assert http.post(route+"/inputs",json={"audio":payload("source.wav",buffer.getvalue())}).status_code == 200
    quote = http.get(route+"/inputs/transcription-estimate").json()
    assert http.post(route+"/inputs/transcribe",json={"approved":True,"estimate_id":quote["estimate_id"]}).status_code == 200
    assert http.post(route+"/analyze").status_code == 200
    narration = http.get(route+"/narration").json()["items"]
    assert [item["text"] for item in narration] == ["Mira arrives.", "Mira explores."]
    assert [item["audio_seconds"] for item in narration] == pytest.approx([.7,3.3])
    for item in narration:
        with wave.open(io.BytesIO(http.get(item["audio_url"]).content)) as audio:
            assert audio.getnframes()/audio.getframerate() == pytest.approx(item["audio_seconds"], abs=.001)
