from pathlib import Path

import pytest

from test_api import client, FixtureAIProvider
from test_production import production, prepare_audio, render_payload
from models.models import AnimationJob, GeneratedAsset, Job, Narration, Project, RenderJob, Video
from services.ai.providers.local_svd import LocalSVDProvider
from services.video_composer_service import VideoComposerService


def automatic_approval(http, project_id, mode="local_animation"):
    path = f"/api/v1/projects/{project_id}/automatic-generation"
    quote = http.get(path, params={"mode": mode}).json()
    result = http.post(path, json={"approved": True, "estimate_id": quote["estimate"]["estimate_id"], "render_mode": mode})
    assert result.status_code == 200, result.text
    assert result.json()["approved"]


def approve_images(http, project_id, stage):
    for asset in http.get(f"/api/v1/projects/{project_id}/{stage}").json():
        assert http.put(f"/api/v1/{stage}/{asset['id']}", json={
            "approved": True, "expected_image_path": asset["image_path"],
        }).status_code == 200


def stage_environment(monkeypatch, sessions, provider=None):
    import api.stage_generation_routes
    monkeypatch.setattr(api.stage_generation_routes, "SessionLocal", sessions)
    monkeypatch.setattr("services.stage_generation_service.create_ai_provider",
                        lambda configuration: provider or FixtureAIProvider())


def test_seconds_are_persisted_and_reach_provider_without_minute_rounding(client, monkeypatch):
    http, sessions, _ = client
    seen = []
    class SecondsProvider(FixtureAIProvider):
        def generate_story(self, prompt, target_minutes):
            seen.append((prompt, target_minutes))
            return super().generate_story(prompt, target_minutes)
    monkeypatch.setattr("services.project_service.create_ai_provider", lambda configuration: SecondsProvider())
    project_id = http.post("/api/v1/projects", json={
        "prompt": "A child explores the moon in a little balloon.", "target_seconds": 17,
    }).json()["project_id"]
    assert http.get(f"/api/v1/projects/{project_id}").json()["target_seconds"] == 17
    assert http.get("/api/v1/projects").json()[0]["target_seconds"] == 17
    assert http.post(f"/api/v1/projects/{project_id}/analyze").status_code == 200
    assert seen[0][1] == pytest.approx(17 / 60)
    with sessions() as db:
        assert db.get(Project, project_id).target_seconds == 17
    for seconds in (0, 601, 1.5):
        assert http.post("/api/v1/projects", json={
            "prompt": "A child explores the moon in a little balloon.", "target_seconds": seconds,
        }).status_code == 422
    assert http.post("/api/v1/projects", json={
        "prompt": "A child explores the moon in a little balloon.", "target_seconds": 17, "target_minutes": 1,
    }).status_code == 422


def test_automatic_images_generate_missing_only_and_require_reviews(client, monkeypatch):
    http, sessions, storage = client
    calls = []
    class Images(FixtureAIProvider):
        def generate_consistent_image(self, prompt, output_path, references):
            calls.append(output_path.name)
            return super().generate_consistent_image(prompt, output_path, references)
    stage_environment(monkeypatch, sessions, Images())
    project_id = http.post("/api/v1/projects", json={"prompt": "A diver visits an old underwater city."}).json()["project_id"]
    path = f"/api/v1/projects/{project_id}"
    automatic_approval(http, project_id)
    assert http.post(path + "/analyze").status_code == 200
    # Upfront consent remains valid when the bounded planned drafts become available.
    assert http.get(path + "/automatic-generation").json()["approved"]
    warning = http.post(path + "/generation/characters", json={})
    assert warning.status_code == 409 and warning.json()["detail"]["stage"] == "story"
    assert not calls
    revision = http.get(path + "/quality").json()["story_revision"]
    http.post(path + "/story/approval", json={"approved": True, "revision": revision})
    result = http.post(path + "/generation/characters", json={})
    assert result.status_code == 200, result.text
    assert http.get(path + "/generation/characters").json()["job"]["status"] == "completed"
    assert len(calls) == 3
    spending = http.get(path).json()["estimated_spend"]
    assert http.post(path + "/generation/characters", json={}).status_code == 200
    assert len(calls) == 3 and http.get(path).json()["estimated_spend"] == spending
    assert http.post(path + "/generation/scenes", json={}).status_code == 409
    approve_images(http, project_id, "characters")
    assert http.post(path + "/generation/scenes", json={}).status_code == 200
    scenes = http.get(path + "/scenes").json()
    assert all(item["image_path"] and not item["approved"] for item in scenes)
    assert len(calls) == 7
    assert http.post(path + "/generation/scenes", json={}).status_code == 200
    assert len(calls) == 7
    directory = storage / "projects" / str(project_id)
    assert len(list(directory.glob("character-*.png"))) == 3
    assert len(list(directory.glob("scene-*.png"))) == 4
    assert len(list(directory.glob("reference-*.png"))) == 3


def test_stage_failure_requires_explicit_retry_and_preserves_completed_assets(client, monkeypatch):
    http, sessions, _ = client
    calls = []
    class FlakyImages(FixtureAIProvider):
        fail = True
        def generate_consistent_image(self, prompt, output_path, references):
            calls.append(output_path.name)
            if len(calls) == 2 and self.fail:
                raise RuntimeError("fixture image failure")
            return super().generate_consistent_image(prompt, output_path, references)
    provider = FlakyImages()
    stage_environment(monkeypatch, sessions, provider)
    project_id = http.post("/api/v1/projects", json={"prompt": "A diver visits an old underwater city."}).json()["project_id"]
    path = f"/api/v1/projects/{project_id}"
    http.post(path + "/analyze")
    automatic_approval(http, project_id)
    revision = http.get(path + "/quality").json()["story_revision"]
    http.post(path + "/story/approval", json={"approved": True, "revision": revision})
    assert http.post(path + "/generation/characters", json={}).status_code == 200
    state = http.get(path + "/generation/characters").json()
    assert state["job"]["status"] == "failed" and state["missing"] == 2
    first = http.get(path + "/characters").json()[0]["image_path"]
    spending = http.get(path).json()["estimated_spend"]
    assert http.post(path + "/generation/characters", json={}).json()["job"]["status"] == "failed"
    assert len(calls) == 2 and http.get(path).json()["estimated_spend"] == spending
    provider.fail = False
    assert http.post(path + "/generation/characters", json={"retry": True}).status_code == 200
    assert http.get(path + "/generation/characters").json()["missing"] == 0
    assert http.get(path + "/characters").json()[0]["image_path"] == first
    assert len(calls) == 4


def test_batch_is_idempotent_while_active_and_blocks_deletion(production, monkeypatch):
    http, sessions, _, project_id, _ = production
    stage_environment(monkeypatch, sessions)
    monkeypatch.setattr("api.stage_generation_routes.run_stage", lambda job_id: None)
    with sessions() as db:
        db.get(Project, project_id).characters[0].image_path = None
        db.commit()
    automatic_approval(http, project_id)
    path = f"/api/v1/projects/{project_id}"
    first = http.post(path + "/generation/characters", json={})
    second = http.post(path + "/generation/characters", json={})
    assert first.status_code == second.status_code == 200
    assert first.json()["job"]["job_id"] == second.json()["job"]["job_id"]
    assert http.request("DELETE", path, json={"approved": True}).status_code == 409
    with sessions() as db:
        assert db.query(Job).filter_by(operation="characters").count() == 1


def test_local_batch_calls_model_for_every_scene_and_render_never_falls_back(production, monkeypatch):
    http, sessions, storage, project_id, _ = production
    stage_environment(monkeypatch, sessions)
    prepare_audio(production)
    automatic_approval(http, project_id)
    calls = []
    monkeypatch.setattr(LocalSVDProvider, "check_ready", lambda self: None)
    def generate(self, image, output, **kwargs):
        calls.append(image)
        output.parent.mkdir(parents=True, exist_ok=True)
        VideoComposerService()._run(["-y", "-f", "lavfi", "-i", "testsrc2=size=128x72:rate=7",
                                    "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output)])
        return {"duration_seconds": 2, "frames": 14, "model": "fixture"}
    monkeypatch.setattr(LocalSVDProvider, "generate_scene_animation", generate)
    path = f"/api/v1/projects/{project_id}"
    denied = http.post(path + "/render", json=render_payload(http, project_id, mode="local_animation"))
    assert denied.status_code == 409 and "EVERY" in denied.json()["detail"]
    result = http.post(path + "/generation/animations", json={})
    assert result.status_code == 200, result.text
    state = http.get(path + "/generation/animations").json()
    assert state["job"]["status"] == "completed", state
    assert len(calls) == 4
    # Generation does not count as review or silently select the clips.
    assert http.post(path + "/render", json=render_payload(http, project_id, mode="local_animation")).status_code == 409
    for scene in http.get(path + "/scenes").json():
        route = path + f"/scenes/{scene['id']}/animation"
        job = http.get(route).json()["job"]
        assert not job["approved"]
        assert http.put(route + "/approval", json={"job_id": job["job_id"], "approved": True}).status_code == 200
    def refuse_stills(*args, **kwargs):
        raise AssertionError("Local-animation export must never compose still images.")
    monkeypatch.setattr(VideoComposerService, "segment", refuse_stills)
    result = http.post(path + "/render", json=render_payload(http, project_id, mode="local_animation"))
    assert result.status_code == 202, result.text
    assert http.get(path + "/render/status").json()["status"] == "completed"
    video = http.get(path + "/video").json()
    assert video["render_mode"] == "local_animation" and video["animated_scene_count"] == 4
    assert video["generated_motion_seconds"] == 4
    assert http.get(path + "/video/download").status_code == 200
    assert http.post(path + "/generation/animations", json={}).status_code == 200
    assert len(calls) == 4


def test_prompt_restart_clears_full_sequence_without_refunding_spend(production):
    http, sessions, storage, project_id, _ = production
    prepare_audio(production)
    path = f"/api/v1/projects/{project_id}"
    assert http.post(path + "/render", json=render_payload(http, project_id)).status_code == 202
    old = http.get(path).json()
    new_prompt = "A musician travels through a city built entirely from clouds."
    payload = {"approved": True, "expected_prompt": old["prompt"], "prompt": new_prompt,
               "target_seconds": 23, "max_budget": 10, "max_wait_minutes": 20}
    wrong = http.put(path + "/prompt", json={**payload, "expected_prompt": "outdated"})
    assert wrong.status_code == 409
    assert http.put(path + "/prompt", json=payload).status_code == 200
    current = http.get(path).json()
    assert current["prompt"] == new_prompt and current["target_seconds"] == 23
    assert current["status"] == "created" and current["estimated_spend"] == old["estimated_spend"]
    assert current["video_url"] is None
    assert not (storage / "projects" / str(project_id)).exists()
    with sessions() as db:
        for model in (Job, RenderJob, Video, GeneratedAsset, Narration, AnimationJob):
            assert db.query(model).filter_by(project_id=project_id).count() == 0
        project = db.get(Project, project_id)
        assert not project.characters and not project.scenes and not project.input_manifest
        assert not project.generation_approval and not project.story_approved
    assert http.post(path + "/analyze").status_code == 200
    assert new_prompt in http.get(path + "/story").json()["summary"]


def test_delete_videos_preserves_assets_then_project_delete_removes_only_its_media(production):
    http, sessions, storage, project_id, _ = production
    prepare_audio(production)
    path = f"/api/v1/projects/{project_id}"
    assert http.post(path + "/render", json=render_payload(http, project_id)).status_code == 202
    other = http.post("/api/v1/projects", json={"prompt": "A second story that must remain intact."}).json()["project_id"]
    other_media = storage / "projects" / str(other) / "keep.png"
    other_media.parent.mkdir(parents=True)
    other_media.write_bytes(b"fixture")
    spending = http.get(path).json()["estimated_spend"]
    assert http.request("DELETE", path + "/video", json={"approved": False}).status_code == 422
    assert http.request("DELETE", path + "/video", json={"approved": True}).status_code == 200
    assert http.get(path + "/video").status_code == 404
    assert http.get(path + "/render/status").json() is None
    assert http.get(path + "/timeline").json()["ready"]
    assert list((storage / "projects" / str(project_id)).glob("scene-*.png"))
    assert not list((storage / "projects" / str(project_id)).glob("video-*.mp4"))
    assert not list((storage / "projects" / str(project_id)).glob("render-*"))
    assert http.get(path).json()["estimated_spend"] == spending
    assert http.request("DELETE", path, json={"approved": True}).status_code == 200
    assert http.get(path).status_code == 404 and other_media.is_file()
    with sessions() as db:
        for model in (Job, RenderJob, Video, GeneratedAsset, Narration, AnimationJob):
            assert db.query(model).filter_by(project_id=project_id).count() == 0
    assert http.request("DELETE", path, json={"approved": True}).status_code == 404


def test_media_move_failure_leaves_project_unchanged(production, monkeypatch):
    http, _, storage, project_id, _ = production
    path = f"/api/v1/projects/{project_id}"
    original = Path.rename
    def fail_project_move(self, target):
        if self == storage / "projects" / str(project_id):
            raise OSError("fixture locked directory")
        return original(self, target)
    monkeypatch.setattr(Path, "rename", fail_project_move)
    response = http.request("DELETE", path, json={"approved": True})
    assert response.status_code == 409 and "no database changes" in response.json()["detail"]
    assert http.get(path).status_code == 200
    assert (storage / "projects" / str(project_id)).is_dir()


def test_legacy_media_copy_does_not_resurrect_deleted_files(tmp_path, monkeypatch):
    import database
    root = tmp_path / "backend"
    legacy_file = root / "database" / "storage" / "projects" / "1" / "video-old.mp4"
    legacy_file.parent.mkdir(parents=True)
    legacy_file.write_bytes(b"legacy")
    storage = root / "storage"
    monkeypatch.setattr(database, "BASE_DIR", root)
    monkeypatch.setattr(database, "STORAGE_DIR", storage)
    database.migrate_legacy_storage()
    copied = storage / "projects" / "1" / "video-old.mp4"
    assert copied.is_file()
    copied.unlink()
    database.migrate_legacy_storage()
    assert not copied.exists() and legacy_file.is_file()


def test_automatic_stage_requires_current_consent_and_budget(production, monkeypatch):
    http, sessions, _, project_id, _ = production
    stage_environment(monkeypatch, sessions)
    path = f"/api/v1/projects/{project_id}"
    with sessions() as db:
        project = db.get(Project, project_id)
        project.characters[0].image_path = None
        project.max_budget = project.estimated_spend
        db.commit()
    assert http.post(path + "/generation/characters", json={}).status_code == 409
    automatic_approval(http, project_id)
    assert http.post(path + "/generation/characters", json={}).status_code == 422
    settings = http.get("/api/v1/settings/ai").json()
    settings.pop("api_key_configured")
    settings["image_model"] = "changed-fixture-model"
    assert http.put("/api/v1/settings/ai", json=settings).status_code == 200
    assert not http.get(path + "/automatic-generation").json()["approved"]
    assert http.post(path + "/generation/characters", json={}).status_code == 409


def test_supplied_story_without_characters_gets_bounded_character_estimate(client):
    http, sessions, _ = client
    project_id = http.post("/api/v1/projects", json={"prompt": "A supplied story needs character definitions."}).json()["project_id"]
    with sessions() as db:
        db.get(Project, project_id).story_summary = "A supplied story, preserved without regeneration."
        db.commit()
    state = http.get(f"/api/v1/projects/{project_id}/automatic-generation").json()
    assert state["characters"] == 6 and state["scenes"] == 12


def test_local_batch_failure_cannot_fall_back_to_still_images(production, monkeypatch):
    http, sessions, _, project_id, _ = production
    stage_environment(monkeypatch, sessions)
    prepare_audio(production)
    automatic_approval(http, project_id)
    calls = []
    monkeypatch.setattr(LocalSVDProvider, "check_ready", lambda self: None)
    def fail(self, image, output, **kwargs):
        calls.append(image)
        raise RuntimeError("fixture CUDA failure")
    monkeypatch.setattr(LocalSVDProvider, "generate_scene_animation", fail)
    path = f"/api/v1/projects/{project_id}"
    assert http.post(path + "/generation/animations", json={}).status_code == 200
    state = http.get(path + "/generation/animations").json()
    assert state["job"]["status"] == "failed" and "CUDA failure" in state["job"]["error"]
    assert http.post(path + "/generation/animations", json={}).json()["job"]["status"] == "failed"
    assert len(calls) == 1
    result = http.post(path + "/render", json=render_payload(http, project_id, mode="local_animation"))
    assert result.status_code == 409 and "EVERY" in result.json()["detail"]
    assert http.get(path + "/video").status_code == 404
    assert http.post(path + "/video", json={"plan": "economy"}).status_code == 409
