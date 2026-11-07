import math
import re
import struct
import subprocess
import time
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from datetime import timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from test_api import FixtureAIProvider, client
from main import app
from models.models import Narration, Project, RenderJob, Video, utc_now
from repositories.production_repository import ProductionRepository
from schemas.production import RenderRequest
from services.render_service import RenderService
from services.video_composer_service import VideoComposerService


class ProductionProvider(FixtureAIProvider):
    text_calls = 0
    speech_calls = 0

    def generate_narration(self, title, description, seconds):
        self.text_calls += 1
        return f"The explorer discovers {title.lower()}."

    def compose_narration(self, context):
        from schemas.quality import NarrativeArc, NarrationScene
        self.text_calls += 1
        return NarrativeArc(opening="A discovery",development="A journey",resolution="A choice",scenes=[
            NarrationScene(scene_id=item["scene_id"],text=f"The explorer discovers {item['title'].lower()}.",
                           bridge="" if index==0 else "After that discovery, the journey continues.")
            for index,item in enumerate(context["scenes"])
        ])

    def generate_speech(self, text, output_path):
        self.speech_calls += 1
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"".join(
                struct.pack("<h", int(12000 * math.sin(index * 2 * math.pi * 440 / 16000)))
                for index in range(4000)
            ))
        return output_path


@pytest.fixture
def production(client, monkeypatch):
    import api.production_routes
    import services.narration_service

    http, sessions, storage = client
    provider = ProductionProvider()
    monkeypatch.setattr(services.narration_service, "create_ai_provider", lambda configuration: provider)
    monkeypatch.setattr(api.production_routes, "SessionLocal", sessions)
    project_id = http.post("/api/v1/projects", json={
        "prompt": "A diver finds a city beneath the ocean.", "max_budget": 10,
    }).json()["project_id"]
    assert http.post(f"/api/v1/projects/{project_id}/analyze").status_code == 200
    revision = http.get(f"/api/v1/projects/{project_id}/quality").json()["story_revision"]
    assert http.post(f"/api/v1/projects/{project_id}/story/approval",json={"approved":True,"revision":revision}).status_code==200
    for character in http.get(f"/api/v1/projects/{project_id}/characters").json():
        assert http.post(f"/api/v1/characters/{character['id']}/portrait").status_code==200
        current = next(item for item in http.get(f"/api/v1/projects/{project_id}/characters").json() if item["id"]==character["id"])
        assert http.put(f"/api/v1/characters/{character['id']}",json={"approved":True,"expected_image_path":current["image_path"]}).status_code==200
    scenes = http.get(f"/api/v1/projects/{project_id}/scenes").json()
    for scene in scenes:
        assert http.post(f"/api/v1/scenes/{scene['id']}/generate").status_code == 200
        current = next(item for item in http.get(f"/api/v1/projects/{project_id}/scenes").json() if item["id"] == scene["id"])
        assert http.put(f"/api/v1/scenes/{scene['id']}", json={
            "approved": True, "expected_image_path": current["image_path"],
        }).status_code == 200
    with sessions() as db:
        for scene in db.get(Project, project_id).scenes:
            scene.estimated_duration = 1
        db.commit()
    return http, sessions, storage, project_id, provider


def approve(http, project_id, operation="narration", regenerate=False):
    estimates = http.get(f"/api/v1/projects/{project_id}/narration").json()
    key = "audio_estimate" if operation == "audio" else "narration_estimate"
    payload = {"approved": True, "estimate_id": estimates[key]["estimate_id"]}
    if operation == "narration":
        payload["regenerate"] = regenerate
    return http.post(f"/api/v1/projects/{project_id}/narration" + ("/audio" if operation == "audio" else ""), json=payload)


def prepare_audio(production):
    http, _, _, project_id, _ = production
    text = approve(http, project_id)
    assert text.status_code == 200, text.text
    audio = approve(http, project_id, "audio")
    assert audio.status_code == 200, audio.text


def render_payload(http, project_id, **kwargs):
    mode = kwargs.pop("mode", "still_images")
    estimate = http.get(f"/api/v1/projects/{project_id}/render/estimate?mode={mode}").json()
    return {"approved": True, "estimate_id": estimate["estimate_id"], "mode": mode, **kwargs}


def test_ffmpeg_emits_live_subsecond_progress(tmp_path):
    composer = VideoComposerService()
    tracking = tmp_path / "encoding.progress"
    values = set()
    with ThreadPoolExecutor(max_workers=1) as pool:
        encoding = pool.submit(composer._run, [
            "-re", "-f", "lavfi", "-i", "color=c=black:s=64x64:r=24",
            "-t", "1.5", "-f", "null", "-",
        ], progress_path=tracking, timeout=10)
        while not encoding.done():
            if tracking.exists():
                for line in tracking.read_text().splitlines():
                    if line.startswith("out_time_us=") and line.partition("=")[2].isdigit():
                        values.add(int(line.partition("=")[2]))
            time.sleep(0.05)
        encoding.result()
    assert len(values) >= 3
    assert any(0 < value < 1_500_000 for value in values)
    assert "progress=end" in tracking.read_text()


def test_render_status_fine_progress_eta_and_partial_records(production, monkeypatch):
    http, sessions, storage, project_id, _ = production
    from services import render_service
    now = utc_now()
    monkeypatch.setattr(render_service, "utc_now", lambda: now)
    tracking = storage / "status.progress"
    with sessions() as db:
        job = RenderJob(
            id="status-test", project_id=project_id, timeline_hash="test", status="running",
            started_at=now - timedelta(seconds=10), progress=40,
            snapshot={"estimate": {"estimated_runtime_seconds": 60}, "attempt_start_progress": 0,
                      "live_progress": {"path": str(tracking), "base": 40, "span": 20, "duration": 10}},
        )
        db.add(job)
        db.commit()
    tracking.write_text("out_time_us=N/A\nout_time_us=5000000\nout_time_us=6")
    status = http.get(f"/api/v1/projects/{project_id}/render/status").json()
    assert status["progress"] == 50.0
    assert status["elapsed_seconds"] == 10
    assert status["estimated_remaining_seconds"] == 10
    tracking.write_text("out_time_us=5432100\n")
    assert http.get(f"/api/v1/projects/{project_id}/render/status").json()["progress"] == 50.9
    tracking.write_text("out_time_us=9999999999\n")
    with sessions() as db:
        job = db.get(RenderJob, "status-test")
        job.snapshot = {**job.snapshot, "live_progress": {
            "path": str(tracking), "base": 80, "span": 19, "duration": 10,
        }}
        db.commit()
    assert http.get(f"/api/v1/projects/{project_id}/render/status").json()["progress"] == 99
    with sessions() as db:
        job = db.get(RenderJob, "status-test")
        job.status = "failed"
        job.completed_at = now
        db.commit()
    failed = http.get(f"/api/v1/projects/{project_id}/render/status").json()
    assert failed["estimated_remaining_seconds"] is None
    assert failed["progress"] == 99
    with sessions() as db:
        job = db.get(RenderJob, "status-test")
        job.status = "queued"
        job.started_at = job.completed_at = None
        job.progress = 80
        job.snapshot = {**job.snapshot, "attempt_start_progress": 80, "live_progress": None}
        db.commit()
    queued = http.get(f"/api/v1/projects/{project_id}/render/status").json()
    assert queued["elapsed_seconds"] == 0
    assert queued["estimated_remaining_seconds"] == 12
    with sessions() as db:
        job = db.get(RenderJob, "status-test")
        job.status = "completed"
        job.progress = 100
        db.commit()
    done = http.get(f"/api/v1/projects/{project_id}/render/status").json()
    assert done["progress"] == 100
    assert done["estimated_remaining_seconds"] == 0


def test_narration_estimates_approval_and_budget(production):
    http, sessions, _, project_id, provider = production
    path = f"/api/v1/projects/{project_id}/narration"
    estimates = http.get(path).json()
    assert estimates["narration_estimate"]["estimated_api_calls"] == 1
    assert provider.text_calls == provider.speech_calls == 0
    assert http.post(path, json={}).status_code == 422
    assert http.post(path, json={"approved": False, "estimate_id": estimates["narration_estimate"]["estimate_id"]}).status_code == 422
    assert http.post(path, json={"approved": True, "estimate_id": "0"*64}).status_code == 409
    with sessions() as db:
        project = db.get(Project, project_id)
        project.max_budget = project.estimated_spend
        db.commit()
    assert approve(http, project_id).status_code == 422
    assert provider.text_calls == 0
    with sessions() as db:
        db.get(Project, project_id).max_budget = 10
        db.commit()
    response = approve(http, project_id)
    assert response.status_code == 200, response.text
    assert len(response.json()["items"]) == 4
    assert provider.text_calls == 1
    assert approve(http, project_id).status_code == 409
    assert provider.text_calls == 1


def test_complete_workflow_downloads_decodable_mp4_with_audio(production):
    http, sessions, _, project_id, provider = production
    prepare_audio(production)
    timeline = http.get(f"/api/v1/projects/{project_id}/timeline").json()
    assert timeline["ready"]
    for scene in timeline["scenes"]:
        assert scene["duration_seconds"] == 1
        assert http.get(scene["audio_url"]).content[:4] == b"RIFF"
    estimate = http.get(f"/api/v1/projects/{project_id}/render/estimate").json()
    assert estimate["estimated_cost"] == 0
    assert estimate["estimated_audio_seconds"] == 1
    assert estimate["estimated_video_seconds"] == 4
    path = f"/api/v1/projects/{project_id}/render"
    assert http.post(path, json={"approved": False, "estimate_id": estimate["estimate_id"]}).status_code == 422
    queued = http.post(path, json=render_payload(http, project_id))
    assert queued.status_code == 202, queued.text
    status = http.get(path + "/status").json()
    assert status["status"] == "completed", status
    assert status["progress"] == 100
    video = http.get(f"/api/v1/projects/{project_id}/video").json()
    assert video["duration_seconds"] == 4
    assert video["audio_seconds"] == 1
    assert [chapter["start_seconds"] for chapter in video["chapters"]] == [0, 1, 2, 3]
    assert [chapter["scene_id"] for chapter in video["chapters"]] == [scene["scene_id"] for scene in timeline["scenes"]]
    assert all(chapter["duration_seconds"] == 1 and chapter["generated_motion_seconds"] == 0
               for chapter in video["chapters"])
    assert video["actual_provider_cost"] is None
    assert video["size_bytes"] > 1000
    download = http.get(video["download_url"])
    assert download.status_code == 200
    assert download.content[4:8] == b"ftyp"
    assert "attachment;" in download.headers["content-disposition"]
    assert http.get(video["url"]).content == download.content
    browser_audio = http.get(video["playback_audio_url"])
    assert browser_audio.status_code == 200
    assert browser_audio.headers["content-type"] == "audio/wav"
    import io
    with wave.open(io.BytesIO(browser_audio.content)) as decoded:
        assert decoded.getframerate() == 16000
        assert decoded.getnchannels() == 1
        assert decoded.getnframes() / decoded.getframerate() == pytest.approx(4, abs=.1)
        assert any(decoded.readframes(decoded.getnframes()))
    assert http.get(video["playback_audio_url"]).content == browser_audio.content
    assert http.get(f"/api/v1/projects/{project_id}/video/audio?render_job_id=old-render").status_code == 409
    with sessions() as db:
        record = db.query(Video).one()
        composer = VideoComposerService()
        result = subprocess.run([composer.ffmpeg, "-hide_banner", "-i", record.file_path], stdin=subprocess.DEVNULL, capture_output=True, text=True)
        assert "Video: h264" in result.stderr
        assert "Audio: aac" in result.stderr
        duration = re.search(r"Duration: (\d+):(\d+):([\d.]+)", result.stderr)
        assert duration
        assert abs(float(duration[3]) - 4) < 0.2
        composer.validate(Path(record.file_path))
        audio = subprocess.run(
            [composer.ffmpeg, "-v", "error", "-i", record.file_path, "-map", "0:a", "-f", "s16le", "-"],
            stdin=subprocess.DEVNULL, capture_output=True,
        )
        assert audio.returncode == 0
        assert any(audio.stdout)
    assert provider.speech_calls == 4
    assert http.get(f"/api/v1/projects/{project_id}/metrics").json()["video_length_seconds"] == 4


def test_timeline_reorder_stale_revision_and_duration_guards(production):
    http, _, _, project_id, _ = production
    prepare_audio(production)
    path = f"/api/v1/projects/{project_id}/timeline"
    original = http.get(path).json()
    ordered = list(reversed(original["scenes"]))
    payload = {"revision": original["revision"], "scenes": ordered}
    response = http.put(path, json=payload)
    assert response.status_code == 200, response.text
    assert [scene["scene_id"] for scene in response.json()["scenes"]] == [scene["scene_id"] for scene in ordered]
    assert http.put(path, json=payload).status_code == 409
    current = response.json()
    assert http.put(path, json={"revision": current["revision"], "scenes": [current["scenes"][0]] * 4}).status_code == 422
    current["scenes"][0]["duration_seconds"] = 0
    assert http.put(path, json=current).status_code == 422


def test_render_requires_ready_media_and_fresh_estimate(production):
    http, _, storage, project_id, _ = production
    path = f"/api/v1/projects/{project_id}/render"
    assert http.post(path, json=render_payload(http, project_id)).status_code == 409
    prepare_audio(production)
    payload = render_payload(http, project_id)
    timeline = http.get(f"/api/v1/projects/{project_id}/timeline").json()
    timeline["scenes"][0]["duration_seconds"] = 2
    assert http.put(f"/api/v1/projects/{project_id}/timeline", json=timeline).status_code == 200
    assert http.post(path, json=payload).status_code == 409
    audio = next((storage / "projects" / str(project_id)).glob("narration-*.wav"))
    audio.unlink()
    assert http.post(path, json=render_payload(http, project_id)).status_code == 409


def test_audio_failure_retries_only_missing_speech(production, monkeypatch):
    http, sessions, _, project_id, provider = production
    assert approve(http, project_id).status_code == 200
    original = provider.generate_speech
    calls = 0

    def fail_second(text, path):
        nonlocal calls
        calls += 1
        if calls == 2:
            from services.ai.providers.base import AIProviderError
            raise AIProviderError("Speech temporarily unavailable")
        return original(text, path)

    monkeypatch.setattr(provider, "generate_speech", fail_second)
    assert approve(http, project_id, "audio").status_code == 502
    with sessions() as db:
        assert sum(item.audio_path is not None for item in db.query(Narration)) == 1
    pending = http.get(f"/api/v1/projects/{project_id}/narration").json()
    assert pending["audio_estimate"]["estimated_api_calls"] == 3
    monkeypatch.setattr(provider, "generate_speech", original)
    assert approve(http, project_id, "audio").status_code == 200
    assert provider.speech_calls == 4


def test_failed_render_resumes_checkpoints_and_preserves_previous_video(production, monkeypatch):
    http, sessions, storage, project_id, _ = production
    prepare_audio(production)
    previous = storage / "projects" / str(project_id) / "previous.mp4"
    previous.write_bytes(b"previous published video")
    with sessions() as db:
        db.get(Project, project_id).video_path = str(previous)
        db.commit()
    original = VideoComposerService.segment
    calls = []

    def fail_second(self, image, audio, seconds, output, index, **kwargs):
        calls.append(index)
        if index == 1:
            raise RuntimeError("Encoder interrupted")
        return original(self, image, audio, seconds, output, index, **kwargs)

    monkeypatch.setattr(VideoComposerService, "segment", fail_second)
    path = f"/api/v1/projects/{project_id}/render"
    assert http.post(path, json=render_payload(http, project_id)).status_code == 202
    status = http.get(path + "/status").json()
    assert status["status"] == "failed"
    assert len(status["completed_scenes"]) == 1
    assert http.get(f"/api/v1/projects/{project_id}/video/download").content == previous.read_bytes()
    monkeypatch.setattr(VideoComposerService, "segment", original)
    with sessions() as db:
        job = db.get(RenderJob, status["job_id"])
        previous_seconds = job.execution_seconds
        assert previous_seconds > 0
        segment = storage / "projects" / str(project_id) / f"render-{job.id}" / f"scene-{job.completed_scenes[0]}.mp4"
        timestamp = segment.stat().st_mtime_ns
    assert http.post(path, json=render_payload(http, project_id, resume_job_id=status["job_id"])).status_code == 202
    assert http.get(path + "/status").json()["status"] == "completed"
    assert segment.stat().st_mtime_ns == timestamp
    assert previous.read_bytes() == b"previous published video"
    with sessions() as db:
        assert db.query(Video).one().generation_seconds >= previous_seconds


def test_concurrent_claim_and_restart_recovery(production):
    http, sessions, _, project_id, _ = production
    prepare_audio(production)
    payload = RenderRequest(**render_payload(http, project_id))
    barrier = Barrier(2)

    def claim(_):
        with sessions() as db:
            barrier.wait()
            try:
                return RenderService(ProductionRepository(db)).start(project_id, payload).job_id
            except HTTPException as error:
                assert error.status_code == 409
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, range(2)))
    assert sum(result is not None for result in results) == 1
    timeline = http.get(f"/api/v1/projects/{project_id}/timeline").json()
    assert http.put(f"/api/v1/projects/{project_id}/timeline", json=timeline).status_code == 409
    assert approve(http, project_id, regenerate=True).status_code == 409
    scene = http.get(f"/api/v1/projects/{project_id}/scenes").json()[0]
    assert http.post(f"/api/v1/scenes/{scene['id']}/regenerate").status_code == 409
    with TestClient(app) as restarted:
        status = restarted.get(f"/api/v1/projects/{project_id}/render/status").json()
        assert status["status"] == "failed"
        assert "Resume" in status["error"]
    response = http.post(f"/api/v1/projects/{project_id}/render", json=render_payload(http, project_id, resume_job_id=status["job_id"]))
    assert response.status_code == 202
    assert http.get(f"/api/v1/projects/{project_id}/render/status").json()["status"] == "completed"


def test_story_edits_invalidate_narration_and_refresh_removes_rows(production):
    http, sessions, _, project_id, _ = production
    prepare_audio(production)
    story = http.get(f"/api/v1/projects/{project_id}/story").json()
    story["scenes"][0]["description"] += " A different event occurs."
    assert http.put(f"/api/v1/projects/{project_id}/story", json=story).status_code == 200
    narration = http.get(f"/api/v1/projects/{project_id}/narration").json()
    assert sum(item["stale"] for item in narration["items"]) == 4
    assert not http.get(f"/api/v1/projects/{project_id}/timeline").json()["ready"]
    assert http.post(f"/api/v1/projects/{project_id}/story/regenerate").status_code == 200
    with sessions() as db:
        assert db.query(Narration).count() == 0


def test_speech_duration_extends_timeline_and_cannot_be_truncated(production, monkeypatch):
    http, _, _, project_id, provider = production
    assert approve(http, project_id).status_code == 200

    def longer_speech(text, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\0\0" * 32000)
        return path

    monkeypatch.setattr(provider, "generate_speech", longer_speech)
    assert approve(http, project_id, "audio").status_code == 200
    timeline = http.get(f"/api/v1/projects/{project_id}/timeline").json()
    assert all(scene["audio_seconds"] == 2 for scene in timeline["scenes"])
    assert all(scene["duration_seconds"] == 3 for scene in timeline["scenes"])
    timeline["scenes"][0]["duration_seconds"] = 2
    response = http.put(f"/api/v1/projects/{project_id}/timeline", json=timeline)
    assert response.status_code == 422
    assert "truncate" in response.json()["detail"]


def test_audio_budget_and_invalid_wav_surface_errors(production, monkeypatch):
    http, sessions, storage, project_id, provider = production
    assert approve(http, project_id).status_code == 200
    with sessions() as db:
        project = db.get(Project, project_id)
        project.max_budget = project.estimated_spend
        db.commit()
    assert approve(http, project_id, "audio").status_code == 422
    assert provider.speech_calls == 0
    with sessions() as db:
        db.get(Project, project_id).max_budget = 10
        db.commit()

    def invalid_speech(text, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"not audio")
        return path

    monkeypatch.setattr(provider, "generate_speech", invalid_speech)
    response = approve(http, project_id, "audio")
    assert response.status_code == 502
    assert "invalid WAV" in response.json()["detail"]
    assert not list((storage / "projects" / str(project_id)).glob("narration-*.wav"))


def test_render_wait_and_storage_limits(production, monkeypatch):
    import services.render_service
    from types import SimpleNamespace

    http, sessions, _, project_id, _ = production
    prepare_audio(production)
    with sessions() as db:
        project = db.get(Project, project_id)
        project.max_wait_minutes = 1
        for scene in project.scenes:
            scene.estimated_duration = 60
        db.commit()
    path = f"/api/v1/projects/{project_id}/render"
    response = http.post(path, json=render_payload(http, project_id))
    assert response.status_code == 422
    assert "wait limit" in response.json()["detail"]
    with sessions() as db:
        db.get(Project, project_id).max_wait_minutes = 20
        db.commit()
    monkeypatch.setattr(services.render_service.shutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    response = http.post(path, json=render_payload(http, project_id))
    assert response.status_code == 422
    assert "storage" in response.json()["detail"]


def test_composer_encodes_visible_zoom_pan_and_fades(tmp_path):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (320, 180), (180, 160, 140))
    draw = ImageDraw.Draw(image)
    for column in range(0, 320, 20):
        draw.rectangle((column, 0, column+9, 179), fill=(20, 220, 100))
    image_path = tmp_path / "pattern.png"
    image.save(image_path)
    audio_path = ProductionProvider().generate_speech("Test narration", tmp_path / "speech.wav")
    output = tmp_path / "scene.mp4"
    composer = VideoComposerService()
    composer.segment(image_path, audio_path, 2, output, 0)
    decoded = subprocess.run(
        [composer.ffmpeg, "-nostdin", "-v", "error", "-i", str(output),
         "-vf", "scale=64:36", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
        stdin=subprocess.DEVNULL, capture_output=True,
    )
    assert decoded.returncode == 0
    frame_bytes = 64 * 36 * 3
    frames = [decoded.stdout[index:index+frame_bytes] for index in range(0, len(decoded.stdout), frame_bytes)]
    assert len(frames) == 48
    assert max(frames[0]) < 5
    assert frames[12] != frames[30]  # Outside both fades: the image itself moves.
    assert sum(frames[-1]) < sum(frames[24]) / 2


def test_streaming_wav_duration_uses_actual_frames_not_header(production, monkeypatch):
    http, _, _, project_id, provider = production
    assert approve(http, project_id).status_code == 200
    generate = provider.generate_speech

    def streaming_header(text, path):
        generate(text, path)
        data = bytearray(path.read_bytes())
        data[4:8] = b"\xff" * 4
        data[40:44] = b"\xff" * 4
        path.write_bytes(data)
        return path

    monkeypatch.setattr(provider, "generate_speech", streaming_header)
    response = approve(http, project_id, "audio")
    assert response.status_code == 200, response.text
    assert all(item["audio_seconds"] == 0.25 for item in response.json()["items"])
