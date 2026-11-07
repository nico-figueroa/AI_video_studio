import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi.testclient import TestClient

from main import app


def confirmed_post(http, path, **kwargs):
    """Explicitly accept review warnings in legacy tests of unrelated behavior."""
    response = http.post(path, **kwargs)
    if response.status_code == 409 and isinstance(response.json().get("detail"), dict):
        detail = response.json()["detail"]
        assert detail["code"] == "review_required"
        return http.post(path,headers={"X-Workflow-Override":detail["confirmation_token"]},**kwargs)
    return response


class FixtureAIProvider:
    def generate_narrative_plan(self, story, characters, target_minutes):
        return None

    def generate_consistent_image(self, prompt, output_path, references):
        if output_path.name.startswith("character-"):
            return self.generate_character_portrait(prompt, output_path)
        return self.generate_scene_image(prompt, output_path)

    def generate_story(self, prompt, target_minutes):
        from schemas.ai_schemas import CharacterSeed, StoryBibleData, ThreeActStructure

        title = "T" * 160 if len(prompt) > 160 else "The Forgotten Ocean"
        return StoryBibleData(
            title=title,
            summary=f"A story shaped by this idea: {prompt}",
            genre="Adventure",
            target_audience="General audience",
            three_act_structure=ThreeActStructure(
                act_one="The discovery changes the protagonist's plans.",
                act_two="The journey reveals a hidden conflict.",
                act_three="A decisive choice changes the future.",
            ),
            main_characters=[
                CharacterSeed(name="The Explorer", role="Protagonist", premise="A curious explorer."),
                CharacterSeed(name="The Guide", role="Ally", premise="A local guide."),
                CharacterSeed(name="The Guardian", role="Antagonist", premise="A protector of secrets."),
            ],
        )

    def generate_character_bible(self, story):
        from schemas.ai_schemas import CharacterBible, CharacterBibleData

        return CharacterBible(characters=[
            CharacterBibleData(
                name=seed.name,
                role=seed.role,
                personality="Curious and determined.",
                appearance="Distinctive field clothing.",
                motivations="Discover the truth.",
                relationships="Connected to the central mystery.",
                portrait_prompt=f"Portrait of {seed.name}, cinematic and consistent.",
            )
            for seed in story.main_characters
        ])

    def generate_scene_plan(self, story, characters, target_minutes):
        from schemas.ai_schemas import ScenePlan, ScenePlanData

        titles = ["The Ordinary World", "A Strange Discovery", "Crossing the Threshold", "A New Beginning"]
        return ScenePlan(scenes=[
            ScenePlanData(
                scene_number=index,
                scene_title=title,
                scene_description=f"{title} advances the story.",
                visual_description=f"A cinematic view of {title.lower()}.",
                image_prompt=f"Create a storyboard frame for {title.lower()}.",
                estimated_duration=30,
            )
            for index, title in enumerate(titles, start=1)
        ])

    def generate_character_portrait(self, prompt, output_path):
        from PIL import Image

        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 64), (60, 90, 70)).save(output_path)
        return output_path

    def generate_scene_image(self, prompt, output_path):
        from PIL import Image

        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 64), (45, 70, 95)).save(output_path)
        return output_path


@pytest.fixture
def client(tmp_path, monkeypatch):
    from database import get_db
    import api.routes
    import main
    import services.image_service
    import services.project_service
    import services.story_service
    import services.video_service
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    storage = tmp_path / "storage"
    (storage / "projects").mkdir(parents=True)
    for module in (main, api.routes, services.image_service, services.project_service, services.video_service):
        monkeypatch.setattr(module, "STORAGE_DIR", storage)
    static = next(route.app for route in app.routes if getattr(route, "name", None) == "storage")
    monkeypatch.setattr(static, "directory", str(storage / "projects"))
    monkeypatch.setattr(static, "all_directories", [str(storage / "projects")])
    monkeypatch.setattr(static, "config_checked", False)
    test_engine = create_engine(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    TestingSession = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(api.routes, "SessionLocal", TestingSession)
    monkeypatch.setattr(api.routes, "create_ai_provider", lambda configuration: FixtureAIProvider())
    monkeypatch.setattr(
        services.project_service, "create_ai_provider",
        lambda configuration: FixtureAIProvider(),
    )
    monkeypatch.setattr(main, "engine", test_engine)
    monkeypatch.setattr(main, "migrate_legacy_storage", lambda: None)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client, TestingSession, storage
    finally:
        app.dependency_overrides.pop(get_db, None)
        test_engine.dispose()


def test_health_and_project_planning_flow(client):
    client, _, _ = client
    assert client.get("/storage/studio.db").status_code == 404
    assert client.get("/storage/projects/../studio.db").status_code == 404
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    created = client.post(
        "/api/v1/projects",
        json={
            "prompt": "A retired astronaut discovers an underwater civilization.",
            "target_minutes": 1,
            "max_budget": 0.5,
            "max_wait_minutes": 20,
        },
    )
    assert created.status_code == 201
    project_id = created.json()["project_id"]
    assert client.post(f"/api/v1/projects/{project_id}/analyze").json()["status"] == "completed"
    estimates = client.get(f"/api/v1/projects/{project_id}/estimates").json()
    assert set(estimates) >= {"economy", "balanced", "premium", "simulated"}
    story = client.get(f"/api/v1/projects/{project_id}/story").json()
    assert len(story["characters"]) == 3
    assert len(story["scenes"]) == 4
    image_without_plan = confirmed_post(client,
        f"/api/v1/scenes/{story['scenes'][0]['id']}/generate"
    )
    assert image_without_plan.status_code == 200
    assert client.post(
        f"/api/v1/projects/{project_id}/select-plan",
        json={"plan": "economy"},
    ).status_code == 200
    assert confirmed_post(client,
        f"/api/v1/scenes/{story['scenes'][0]['id']}/generate"
    ).status_code == 200
    blocked = client.post(
        f"/api/v1/projects/{project_id}/select-plan",
        json={"plan": "balanced"},
    )
    assert blocked.status_code == 422
    queued = client.post(
        f"/api/v1/projects/{project_id}/video",
        json={"plan": "economy"},
    )
    assert queued.status_code == 202
    job_id = queued.json()["job_id"]
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "completed", job.get("error")
    video = client.get(job["video_url"])
    assert video.status_code == 200
    assert video.content[4:8] == b"ftyp"
    assert client.get(f"/api/v1/projects/{project_id}/metrics").json()["actual_cost"] == 0
    assert client.get(f"/api/v1/projects/{project_id}").json()["status"] == "completed"
    story["summary"] = "A revised story, saved by its creator."
    assert client.put(f"/api/v1/projects/{project_id}/story", json=story).json()["updated"]
    assert client.get(f"/api/v1/projects/{project_id}/story").json()["summary"] == story["summary"]
    assert client.post(f"/api/v1/projects/{project_id}/story/regenerate").status_code == 200
    refreshed = client.get(f"/api/v1/projects/{project_id}").json()
    assert refreshed["status"] == "analysis_complete"
    assert refreshed["selected_plan"] is None
    assert refreshed["video_url"] is None

    constrained = client.post(
        "/api/v1/projects",
        json={
            "prompt": "A gardener finds a doorway beneath a glasshouse.",
            "target_minutes": 1,
            "max_budget": 5,
            "max_wait_minutes": 3,
        },
    ).json()["project_id"]
    client.post(f"/api/v1/projects/{constrained}/analyze")
    too_slow = client.post(
        f"/api/v1/projects/{constrained}/select-plan",
        json={"plan": "balanced"},
    )
    assert too_slow.status_code == 422


def test_planning_and_image_requests_enforce_wait_limits(client):
    from models.models import Project

    client, sessions, _ = client
    too_short = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "max_budget": 5,
        "max_wait_minutes": 1,
    }).json()["project_id"]
    response = client.post(f"/api/v1/projects/{too_short}/analyze")
    assert response.status_code == 422
    rejected_project = client.get(f"/api/v1/projects/{too_short}").json()
    assert rejected_project["estimated_spend"] == 0
    assert rejected_project["status"] == "created"

    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "max_budget": 5,
        "max_wait_minutes": 3,
    }).json()["project_id"]
    assert client.post(f"/api/v1/projects/{project_id}/analyze").status_code == 200
    with sessions() as db:
        db.get(Project, project_id).max_wait_minutes = 1
        db.commit()
    spend_before = client.get(f"/api/v1/projects/{project_id}").json()["estimated_spend"]
    character_id = client.get(f"/api/v1/projects/{project_id}/characters").json()[0]["id"]
    scene_id = client.get(f"/api/v1/projects/{project_id}/scenes").json()[0]["id"]
    assert confirmed_post(client,f"/api/v1/characters/{character_id}/portrait").status_code == 422
    assert confirmed_post(client,f"/api/v1/scenes/{scene_id}/generate").status_code == 422
    assert client.get(f"/api/v1/projects/{project_id}").json()["estimated_spend"] == spend_before


def test_image_reservation_rounds_cumulative_spend_before_budget_check(client):
    from api.routes import reserve_estimated_cost
    from fastapi import HTTPException
    from models.models import Project
    from services.ai.estimation_service import GenerationEstimate
    from services.project_service import ProjectService

    _, sessions, _ = client
    with sessions() as db:
        project = Project(
            prompt="A sufficiently long project prompt.",
            max_budget=0.179,
            max_wait_minutes=10,
            estimated_spend=0.139,
        )
        db.add(project)
        db.commit()
        reserve_estimated_cost(
            project,
            db,
            GenerationEstimate(
                operation="scene_image",
                estimated_cost=0.04,
                estimated_minutes=1.5,
                estimated_model_usage="1 image",
                estimated_api_calls=1,
                notes="test",
            ),
        )
        db.refresh(project)
        assert project.estimated_spend == 0.179

    with pytest.raises(HTTPException) as error:
        ProjectService._reserve_estimated_cost(project, 0.0001)
    assert error.value.status_code == 422


def test_story_edit_schema_matches_database_bounds(client):
    client, _, _ = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
    }).json()["project_id"]
    assert client.post(f"/api/v1/projects/{project_id}/analyze").status_code == 200
    original = client.get(f"/api/v1/projects/{project_id}/story").json()

    invalid_edits = []
    character_name = {**original["characters"][0], "name": "C" * 121}
    invalid_edits.append({**original, "characters": [character_name, *original["characters"][1:]]})
    scene_title = {**original["scenes"][0], "title": "S" * 161}
    invalid_edits.append({**original, "scenes": [scene_title, *original["scenes"][1:]]})
    invalid_duration = {**original["scenes"][0], "estimated_duration": 3601}
    invalid_edits.append({**original, "scenes": [invalid_duration, *original["scenes"][1:]]})

    for payload in invalid_edits:
        assert client.put(f"/api/v1/projects/{project_id}/story", json=payload).status_code == 422


def test_ai_settings_reject_whitespace_only_model_names(client):
    client, _, _ = client
    settings = {
        "provider": "openai",
        "model": "gpt-5",
        "image_model": "gpt-image-1",
        "default_budget": 5,
        "default_wait_minutes": 20,
    }
    for field in ("model", "image_model"):
        invalid = {**settings, field: "   "}
        assert client.put("/api/v1/settings/ai", json=invalid).status_code == 422


def test_empty_character_bible_stops_before_scene_plan_call(client, monkeypatch):
    from schemas.ai_schemas import CharacterBible

    client, _, _ = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "max_budget": 5,
    }).json()["project_id"]
    scene_plan_called = []
    monkeypatch.setattr(
        FixtureAIProvider,
        "generate_character_bible",
        lambda self, story: CharacterBible(characters=[]),
    )
    monkeypatch.setattr(
        FixtureAIProvider,
        "generate_scene_plan",
        lambda *args: scene_plan_called.append(True),
    )

    response = client.post(f"/api/v1/projects/{project_id}/analyze")
    assert response.status_code == 502
    assert not scene_plan_called


def test_ai_settings_estimates_and_project_budget_defaults(client, monkeypatch):
    client, _, _ = client
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-returned")
    settings = client.get("/api/v1/settings/ai").json()
    assert settings["provider"] == "openai"
    assert settings["api_key_configured"] is True
    assert "test-key-not-returned" not in str(settings)

    updated = client.put("/api/v1/settings/ai", json={
        "provider": "openai",
        "model": "gpt-5-test",
        "image_model": "gpt-image-test",
        "default_budget": 7.5,
        "default_wait_minutes": 35,
    })
    assert updated.status_code == 200
    assert updated.json()["default_budget"] == 7.5

    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
    }).json()["project_id"]
    project = client.get(f"/api/v1/projects/{project_id}").json()
    assert project["status"] == "created"
    assert project["max_budget"] == 7.5
    assert project["max_wait_minutes"] == 35

    estimates = client.get(
        f"/api/v1/projects/{project_id}/generation-estimates"
    ).json()
    assert set(estimates) == {
        "planning", "story", "characters", "scenes", "character_portrait",
        "scene_image", "all_images",
    }
    assert estimates["planning"]["estimated_api_calls"] == 3
    assert "gpt-5-test" in estimates["story"]["estimated_model_usage"]
    assert estimates["all_images"]["estimated_api_calls"] == 7

    constrained = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "max_budget": 0.001,
    }).json()["project_id"]
    rejected = client.post(f"/api/v1/projects/{constrained}/analyze")
    assert rejected.status_code == 422
    assert client.get(f"/api/v1/projects/{constrained}").json()["status"] == "created"


def test_image_estimates_charge_only_for_image_calls(client, monkeypatch):
    from types import SimpleNamespace
    from services.ai.estimation_service import AIEstimationService

    client, _, _ = client
    monkeypatch.setenv("ESTIMATED_TEXT_USD_PER_1K_TOKENS", "0.002")
    monkeypatch.setenv("ESTIMATED_IMAGE_USD_PER_IMAGE", "0.04")
    estimator = AIEstimationService()
    configuration = SimpleNamespace(model="text-model", image_model="image-model")

    portrait = estimator.estimate("character_portrait", configuration)
    scene = estimator.estimate("scene_image", configuration)
    all_images = estimator.estimate(
        "all_images", configuration, character_count=3, scene_count=4
    )
    assert portrait.estimated_cost == 0.04
    assert scene.estimated_cost == 0.04
    assert all_images.estimated_cost == 7 * portrait.estimated_cost


def test_ai_configuration_concurrent_first_access_is_singleton(client):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from models.models import AIConfiguration
    from services.ai.configuration import get_ai_configuration

    _, sessions, _ = client
    barrier = Barrier(2)

    def initialize():
        with sessions() as db:
            barrier.wait()
            configuration = get_ai_configuration(db)
            db.commit()
            return configuration.id

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(lambda _: initialize(), range(2))) == [1, 1]
    with sessions() as db:
        assert db.query(AIConfiguration).count() == 1


def test_interrupted_planning_is_recovered_and_can_be_retried(client):
    from models.models import Project

    client, sessions, _ = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
    }).json()["project_id"]
    with sessions() as db:
        db.get(Project, project_id).status = "planning"
        db.commit()
    with TestClient(app) as restarted:
        assert restarted.get(f"/api/v1/projects/{project_id}").json()["status"] == "analysis_failed"
        assert restarted.post(f"/api/v1/projects/{project_id}/analyze").status_code == 200
        assert restarted.get(f"/api/v1/projects/{project_id}").json()["status"] == "analysis_complete"


def test_interrupted_refresh_with_scenes_retries_as_refresh(client):
    from models.models import Project

    client, sessions, _ = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "max_budget": 5,
    }).json()["project_id"]
    assert client.post(f"/api/v1/projects/{project_id}/analyze").status_code == 200
    with sessions() as db:
        db.get(Project, project_id).status = "planning"
        db.commit()
    with TestClient(app) as restarted:
        assert restarted.get(f"/api/v1/projects/{project_id}").json()["status"] == "analysis_failed"
        assert restarted.post(f"/api/v1/projects/{project_id}/analyze").status_code == 200
        assert restarted.get(f"/api/v1/projects/{project_id}").json()["status"] == "analysis_complete"
        assert len(restarted.get(f"/api/v1/projects/{project_id}/story").json()["scenes"]) == 4


def test_refresh_reservation_uses_visible_planning_estimate(client):
    from models.models import Project

    client, sessions, _ = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "max_budget": 5,
    }).json()["project_id"]
    assert client.post(f"/api/v1/projects/{project_id}/analyze").status_code == 200
    with sessions() as db:
        project = db.get(Project, project_id)
        db.delete(project.characters[-1])
        db.delete(project.scenes[-1])
        db.commit()
    planning_estimate = client.get(
        f"/api/v1/projects/{project_id}/generation-estimates"
    ).json()["planning"]["estimated_cost"]
    spend_before = client.get(f"/api/v1/projects/{project_id}").json()["estimated_spend"]
    assert client.post(f"/api/v1/projects/{project_id}/story/regenerate").status_code == 200
    spend_after = client.get(f"/api/v1/projects/{project_id}").json()["estimated_spend"]
    assert round(spend_after - spend_before, 4) == planning_estimate


def test_story_edits_synchronize_unchanged_generation_prompts(client):
    client, _, _ = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "max_budget": 5,
    }).json()["project_id"]
    assert client.post(f"/api/v1/projects/{project_id}/analyze").status_code == 200
    story = client.get(f"/api/v1/projects/{project_id}/story").json()
    character = story["characters"][0]
    character["name"] = "New Explorer"
    character["description"] = "A revised character description."
    character["appearance"] = "Silver expedition suit"
    scene = story["scenes"][0]
    scene["title"] = "The New Signal"
    scene["description"] = "A revised scene description."
    scene["visual_description"] = "A silver diver studies a luminous display."

    assert client.put(f"/api/v1/projects/{project_id}/story", json=story).status_code == 200
    saved = client.get(f"/api/v1/projects/{project_id}/story").json()
    assert saved["characters"][0]["portrait_prompt"] == (
        "New Explorer A revised character description. Silver expedition suit"
    )
    assert saved["scenes"][0]["image_prompt"] == (
        "The New Signal A revised scene description. "
        "A silver diver studies a luminous display."
    )


def test_scene_generation_rechecks_and_refunds_duplicate_reservation(client, monkeypatch):
    from api.routes import generate_scene_image
    from models.models import Scene
    import api.routes

    client, sessions, _ = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "max_budget": 5,
    }).json()["project_id"]
    assert client.post(f"/api/v1/projects/{project_id}/analyze").status_code == 200
    scene_id = client.get(f"/api/v1/projects/{project_id}/scenes").json()[0]["id"]
    spend_before = client.get(f"/api/v1/projects/{project_id}").json()["estimated_spend"]
    reserve = api.routes.reserve_estimated_cost
    provider_calls = []

    def reserve_then_complete_elsewhere(project, db, estimate):
        reserve(project, db, estimate)
        with sessions() as other_db:
            scene = other_db.get(Scene, scene_id)
            scene.image_path = f"/storage/projects/{project_id}/scene-{scene_id}.png"
            other_db.commit()

    monkeypatch.setattr(api.routes, "reserve_estimated_cost", reserve_then_complete_elsewhere)
    with sessions() as db:
        from models.models import Project
        for character in db.get(Project,project_id).characters:
            character.approved = True
        db.commit()
    monkeypatch.setattr(
        FixtureAIProvider,
        "generate_scene_image",
        lambda *args, **kwargs: provider_calls.append("called"),
    )
    with sessions() as db:
        generate_scene_image(scene_id, db)

    assert provider_calls == []
    assert client.get(f"/api/v1/projects/{project_id}").json()["estimated_spend"] == spend_before


def test_portrait_generation_refunds_reservation_if_character_was_deleted(client, monkeypatch):
    from fastapi import HTTPException
    from api.routes import generate_portrait
    from models.models import Character
    import api.routes

    client, sessions, _ = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "max_budget": 5,
    }).json()["project_id"]
    assert client.post(f"/api/v1/projects/{project_id}/analyze").status_code == 200
    character_id = client.get(f"/api/v1/projects/{project_id}/characters").json()[0]["id"]
    spend_before = client.get(f"/api/v1/projects/{project_id}").json()["estimated_spend"]
    reserve = api.routes.reserve_estimated_cost

    def reserve_then_delete(project, db, estimate):
        reserve(project, db, estimate)
        with sessions() as other_db:
            other_db.delete(other_db.get(Character, character_id))
            other_db.commit()

    monkeypatch.setattr(api.routes, "reserve_estimated_cost", reserve_then_delete)
    with sessions() as db:
        from models.models import Project
        db.get(Project,project_id).story_approved = True
        db.commit()
    with sessions() as db, pytest.raises(HTTPException) as error:
        generate_portrait(character_id, db)

    assert error.value.status_code == 404
    assert client.get(f"/api/v1/projects/{project_id}").json()["estimated_spend"] == spend_before


def test_active_jobs_block_refresh_and_duplicate_exports(client):
    from models.models import Job
    from sqlalchemy.exc import IntegrityError

    client, sessions, _ = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "target_minutes": 1, "max_budget": 5, "max_wait_minutes": 20,
    }).json()["project_id"]
    assert client.post(f"/api/v1/projects/{project_id}/analyze").status_code == 200
    assert client.post(f"/api/v1/projects/{project_id}/select-plan", json={"plan": "economy"}).status_code == 200
    with sessions() as db:
        db.add(Job(id="active", project_id=project_id, status="running"))
        db.commit()
        db.add(Job(id="duplicate", project_id=project_id, status="queued"))
        with pytest.raises(IntegrityError):
            db.commit()
    assert client.get(f"/api/v1/projects/{project_id}/active-job").json()["job_id"] == "active"
    assert client.post(f"/api/v1/projects/{project_id}/video", json={"plan": "economy"}).status_code == 409
    assert client.post(f"/api/v1/projects/{project_id}/story/regenerate").status_code == 409
    assert client.post(f"/api/v1/projects/{project_id}/analyze?refresh=true").status_code == 409
    assert len(client.get(f"/api/v1/projects/{project_id}/story").json()["scenes"]) == 4


def test_select_plan_locks_project_before_validation(client, monkeypatch):
    from repositories.project_repository import ProjectRepository
    from services.project_service import ProjectService

    client, sessions, _ = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
    }).json()["project_id"]
    assert client.post(f"/api/v1/projects/{project_id}/analyze").status_code == 200
    events = []
    lock_project = ProjectRepository.lock_project
    require_no_active_job = ProjectRepository.require_no_active_job

    def lock_then_record(repository, current_project_id):
        events.append("lock")
        return lock_project(repository, current_project_id)

    def check_job_then_record(repository, current_project_id):
        events.append("check")
        return require_no_active_job(repository, current_project_id)

    monkeypatch.setattr(ProjectRepository, "lock_project", lock_then_record)
    monkeypatch.setattr(ProjectRepository, "require_no_active_job", check_job_then_record)
    with sessions() as db:
        ProjectService(ProjectRepository(db)).select_plan(project_id, "economy")
    assert events[:2] == ["lock", "check"]


def test_portrait_regeneration_requires_reapproval(client):
    client, _, _ = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "target_minutes": 1, "max_budget": 5, "max_wait_minutes": 20,
    }).json()["project_id"]
    client.post(f"/api/v1/projects/{project_id}/analyze")
    client.post(f"/api/v1/projects/{project_id}/select-plan", json={"plan": "economy"})
    character_id = client.get(f"/api/v1/projects/{project_id}/characters").json()[0]["id"]
    assert confirmed_post(client,f"/api/v1/characters/{character_id}/portrait").status_code == 200
    character = client.get(f"/api/v1/projects/{project_id}/characters").json()[0]
    assert client.put(
        f"/api/v1/characters/{character_id}",
        json={"approved": True, "expected_image_path": character["image_path"]},
    ).status_code == 200
    assert client.get(f"/api/v1/projects/{project_id}/characters").json()[0]["approved"]
    assert confirmed_post(client,f"/api/v1/characters/{character_id}/portrait").status_code == 200
    assert not client.get(f"/api/v1/projects/{project_id}/characters").json()[0]["approved"]


def test_approval_rejects_stale_character_and_scene_image_versions(client):
    client, _, _ = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "max_budget": 5,
    }).json()["project_id"]
    assert client.post(f"/api/v1/projects/{project_id}/analyze").status_code == 200
    character = client.get(f"/api/v1/projects/{project_id}/characters").json()[0]
    scene = client.get(f"/api/v1/projects/{project_id}/scenes").json()[0]
    assert confirmed_post(client,f"/api/v1/characters/{character['id']}/portrait").status_code == 200
    assert confirmed_post(client,f"/api/v1/scenes/{scene['id']}/generate").status_code == 200
    character = client.get(f"/api/v1/projects/{project_id}/characters").json()[0]
    scene = client.get(f"/api/v1/projects/{project_id}/scenes").json()[0]

    stale_character = client.put(
        f"/api/v1/characters/{character['id']}",
        json={"approved": True, "expected_image_path": "/old-character.png"},
    )
    stale_scene = client.put(
        f"/api/v1/scenes/{scene['id']}",
        json={"approved": True, "expected_image_path": "/old-scene.png"},
    )
    assert stale_character.status_code == 409
    assert stale_scene.status_code == 409

    assert client.put(
        f"/api/v1/characters/{character['id']}",
        json={"approved": True, "expected_image_path": character["image_path"]},
    ).status_code == 200
    assert client.put(
        f"/api/v1/scenes/{scene['id']}",
        json={"approved": True, "expected_image_path": scene["image_path"]},
    ).status_code == 200


def test_failed_replacement_preserves_video_and_fractional_durations(client, monkeypatch):
    import subprocess
    from models.models import Project, Scene
    from services.video_service import VideoService

    _, _, storage = client
    project = Project(id=12, prompt="A sufficiently long story")
    scenes = [Scene(id=i, title=f"Scene {i}", description="A scene", scene_number=i) for i in range(1, 9)]
    previous = storage / "projects" / "12" / "previous.mp4"
    previous.parent.mkdir(parents=True)
    previous.write_bytes(b"old video")
    project.video_path = str(previous)
    captured = []

    def fail(command, **kwargs):
        listing = Path(command[command.index("-i") + 1])
        captured.append(listing.read_text(encoding="utf-8"))
        Path(command[-1]).write_bytes(b"partial")
        return subprocess.CompletedProcess(command, 1, "", "failure")

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(RuntimeError, match="FFmpeg video export failed"):
        VideoService().compose(project, scenes, 5)
    assert captured[0].count("duration 37.5\n") == 8
    assert previous.read_bytes() == b"old video"
    assert list(previous.parent.glob("video-*.mp4")) == []


def test_export_with_eight_scenes_has_full_five_minute_duration(client, monkeypatch):
    import re
    import subprocess
    from PIL import Image
    from models.models import Project, Scene
    from services.video_service import VideoService

    _, _, storage = client
    directory = storage / "projects" / "13"
    directory.mkdir()
    scenes = []
    for i in range(1, 9):
        Image.new("RGB", (64, 36)).save(directory / f"scene-{i}.png")
        scenes.append(Scene(id=i, title=f"Scene {i}", description="A scene", scene_number=i, image_path="present"))
    service = VideoService()
    actual_run = subprocess.run

    def small_output(command, **kwargs):
        command[command.index("-vf") + 1] = "scale=64:36,format=yuv420p"
        return actual_run(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", small_output)
    output = service.compose(Project(id=13, prompt="A sufficiently long story"), scenes, 5)
    probe = actual_run([service.ffmpeg, "-i", str(output)], stdin=subprocess.DEVNULL, capture_output=True, text=True)
    duration = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", probe.stderr)
    assert duration is not None
    seconds = int(duration[1]) * 3600 + int(duration[2]) * 60 + float(duration[3])
    assert abs(seconds - 300) <= 1 / 12


def test_download_is_attachment(client):
    from models.models import Project

    client, sessions, storage = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
    }).json()["project_id"]
    video = storage / "projects" / str(project_id) / "video.mp4"
    video.parent.mkdir()
    video.write_bytes(b"video")
    with sessions() as db:
        db.get(Project, project_id).video_path = str(video)
        db.commit()
    response = client.get(f"/api/v1/projects/{project_id}/video/download")
    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.content == b"video"


def test_concurrent_video_requests_claim_only_one_job(client):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi import BackgroundTasks, HTTPException
    from api.routes import start_video
    from schemas.schemas import VideoRequest

    client, sessions, _ = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "target_minutes": 1, "max_budget": 5, "max_wait_minutes": 20,
    }).json()["project_id"]
    client.post(f"/api/v1/projects/{project_id}/analyze")
    client.post(f"/api/v1/projects/{project_id}/select-plan", json={"plan": "economy"})
    barrier = Barrier(2)

    def claim():
        with sessions() as db:
            barrier.wait()
            try:
                start_video(project_id, VideoRequest(plan="economy"), BackgroundTasks(), db)
                return 202
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: claim(), range(2))) == [202, 409]


def test_refresh_and_export_are_mutually_exclusive(client):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi import BackgroundTasks, HTTPException
    from api.routes import start_video
    from repositories.project_repository import ProjectRepository
    from schemas.schemas import VideoRequest
    from services.project_service import ProjectService

    client, sessions, _ = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "target_minutes": 1, "max_budget": 5, "max_wait_minutes": 20,
    }).json()["project_id"]
    client.post(f"/api/v1/projects/{project_id}/analyze")
    client.post(f"/api/v1/projects/{project_id}/select-plan", json={"plan": "economy"})
    barrier = Barrier(2)

    def run(operation):
        with sessions() as db:
            barrier.wait()
            try:
                if operation == "refresh":
                    ProjectService(ProjectRepository(db)).analyze(project_id, refresh=True)
                else:
                    start_video(project_id, VideoRequest(plan="economy"), BackgroundTasks(), db)
                return 200
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, ("refresh", "export"))) == [200, 409]


def test_restart_reconciles_interrupted_job(client):
    from models.models import Job, Project

    client, sessions, _ = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
    }).json()["project_id"]
    with sessions() as db:
        db.get(Project, project_id).status = "generating"
        db.add(Job(id="interrupted", project_id=project_id, status="running"))
        db.commit()
    with TestClient(app) as restarted:
        job = restarted.get("/api/v1/jobs/interrupted").json()
        assert job["status"] == "failed"
        assert "retry" in job["error"]
        assert restarted.get(f"/api/v1/projects/{project_id}/active-job").json() is None
        assert restarted.get(f"/api/v1/projects/{project_id}").json()["status"] == "generation_failed"


def test_legacy_storage_is_copied_and_paths_are_rewritten(tmp_path, monkeypatch):
    import database

    legacy = tmp_path / "database" / "storage"
    old_video = legacy / "projects" / "1" / "final-video.mp4"
    old_video.parent.mkdir(parents=True)
    old_video.write_bytes(b"old video")
    legacy_db = legacy / "studio.db"
    legacy_db.write_bytes(b"legacy SQLite database backup")
    monkeypatch.setattr(database, "BASE_DIR", tmp_path)
    monkeypatch.setattr(database, "STORAGE_DIR", tmp_path / "storage")
    database.migrate_legacy_storage()
    new_video = tmp_path / "storage" / "projects" / "1" / "final-video.mp4"
    assert new_video.read_bytes() == old_video.read_bytes()
    assert old_video.exists()
    assert legacy_db.read_bytes() == b"legacy SQLite database backup"


def test_unsafe_requests_reject_untrusted_browser_origins(client):
    client, _, _ = client
    project_id = client.post("/api/v1/projects", json={"prompt": "A gardener finds a doorway."}).json()["project_id"]
    path = f"/api/v1/projects/{project_id}/analyze"
    for headers in (
        {"Origin": "https://attacker.example", "Content-Type": "application/x-www-form-urlencoded"},
        {"Origin": "null"},
        {"Sec-Fetch-Site": "cross-site"},
    ):
        response = client.post(path, headers=headers)
        assert response.status_code == 403
        assert response.json()["detail"] == "Request origin is not allowed."
    assert client.get(f"/api/v1/projects/{project_id}").json()["status"] == "created"
    response = client.post(path, headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert client.post(path, headers={"Origin": "http://localhost:8000"}).status_code == 200
    assert client.post(path).status_code == 200


@pytest.mark.parametrize("status", ["queued", "running"])
def test_active_jobs_block_story_plan_and_scene_mutations(client, status):
    from models.models import Job, Project

    client, sessions, storage = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "target_minutes": 1, "max_budget": 5, "max_wait_minutes": 20,
    }).json()["project_id"]
    client.post(f"/api/v1/projects/{project_id}/analyze")
    client.post(f"/api/v1/projects/{project_id}/select-plan", json={"plan": "economy"})
    story = client.get(f"/api/v1/projects/{project_id}/story").json()
    scene_id = story["scenes"][0]["id"]
    assert confirmed_post(client,f"/api/v1/scenes/{scene_id}/generate").status_code == 200
    image = storage / "projects" / str(project_id) / f"scene-{scene_id}.png"
    original_image = image.read_bytes()
    with sessions() as db:
        db.get(Project, project_id).status = "generating"
        db.add(Job(id=f"active-{status}", project_id=project_id, status=status))
        db.commit()
    story["scenes"][0]["title"] = "Changed while exporting"
    assert client.put(f"/api/v1/projects/{project_id}/story", json=story).status_code == 409
    assert client.post(f"/api/v1/projects/{project_id}/select-plan", json={"plan": "balanced"}).status_code == 409
    assert confirmed_post(client,f"/api/v1/scenes/{scene_id}/regenerate").status_code == 409
    assert confirmed_post(client,f"/api/v1/scenes/{scene_id}/generate").status_code == 409
    assert image.read_bytes() == original_image
    project = client.get(f"/api/v1/projects/{project_id}").json()
    assert project["status"] == "generating"
    assert project["selected_plan"] == "economy"
    assert client.get(f"/api/v1/projects/{project_id}/story").json()["scenes"][0]["title"] != story["scenes"][0]["title"]


def test_story_edits_invalidate_only_changed_artwork(client):
    client, _, _ = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "target_minutes": 1, "max_budget": 5, "max_wait_minutes": 20,
    }).json()["project_id"]
    client.post(f"/api/v1/projects/{project_id}/analyze")
    client.post(f"/api/v1/projects/{project_id}/select-plan", json={"plan": "economy"})
    story = client.get(f"/api/v1/projects/{project_id}/story").json()
    for character in story["characters"][:2]:
        confirmed_post(client,f"/api/v1/characters/{character['id']}/portrait")
        updated = client.get(f"/api/v1/projects/{project_id}/characters").json()
        image_path = next(item["image_path"] for item in updated if item["id"] == character["id"])
        client.put(
            f"/api/v1/characters/{character['id']}",
            json={"approved": True, "expected_image_path": image_path},
        )
    for scene in story["scenes"][:2]:
        confirmed_post(client,f"/api/v1/scenes/{scene['id']}/generate")
        updated = client.get(f"/api/v1/projects/{project_id}/scenes").json()
        image_path = next(item["image_path"] for item in updated if item["id"] == scene["id"])
        client.put(
            f"/api/v1/scenes/{scene['id']}",
            json={"approved": True, "expected_image_path": image_path},
        )
    story = client.get(f"/api/v1/projects/{project_id}/story").json()
    assert client.put(f"/api/v1/projects/{project_id}/story", json=story).status_code == 200
    assert client.get(f"/api/v1/projects/{project_id}/story").json() == story
    story["characters"][0]["description"] += " Changed."
    story["scenes"][0]["title"] += " Changed"
    assert client.put(f"/api/v1/projects/{project_id}/story", json=story).status_code == 200
    updated = client.get(f"/api/v1/projects/{project_id}/story").json()
    assert updated["characters"][0]["image_path"] is None
    assert updated["characters"][0]["approved"] is False
    assert updated["characters"][1] == story["characters"][1]
    assert updated["scenes"][0]["image_path"] is None
    assert updated["scenes"][0]["approved"] is False
    assert updated["scenes"][0]["status"] == "pending"
    assert updated["scenes"][1] == story["scenes"][1]


def test_long_generated_title_can_be_saved(client):
    client, _, _ = client
    project_id = client.post("/api/v1/projects", json={"prompt": "a" * 1000}).json()["project_id"]
    assert client.post(f"/api/v1/projects/{project_id}/analyze").status_code == 200
    story = client.get(f"/api/v1/projects/{project_id}/story").json()
    assert len(story["title"]) == 160
    assert client.put(f"/api/v1/projects/{project_id}/story", json=story).status_code == 200


def test_concurrent_initial_analysis_is_atomic(client):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from models.models import Character, Estimate, Scene
    from repositories.project_repository import ProjectRepository
    from services.project_service import ProjectService

    client, sessions, _ = client
    project_id = client.post("/api/v1/projects", json={"prompt": "A gardener finds a doorway."}).json()["project_id"]
    barrier = Barrier(2)

    def analyze(_):
        with sessions() as db:
            barrier.wait()
            ProjectService(ProjectRepository(db)).analyze(project_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(analyze, range(2)))
    with sessions() as db:
        assert db.query(Character).filter_by(project_id=project_id).count() == 3
        assert db.query(Scene).filter_by(project_id=project_id).count() == 4
        assert db.query(Estimate).filter_by(project_id=project_id).count() == 3


def test_analysis_rolls_back_story_if_estimation_fails(client, monkeypatch):
    from models.models import Character, Estimate, Project, Scene
    from services.estimation_service import EstimationService

    client, sessions, _ = client
    project_id = client.post("/api/v1/projects", json={"prompt": "A gardener finds a doorway."}).json()["project_id"]

    def fail(*args):
        raise RuntimeError("estimation failed")

    monkeypatch.setattr(EstimationService, "calculate", fail)
    with pytest.raises(RuntimeError, match="estimation failed"):
        client.post(f"/api/v1/projects/{project_id}/analyze")
    with sessions() as db:
        assert db.get(Project, project_id).status == "created"
        assert db.query(Character).count() == 0
        assert db.query(Scene).count() == 0
        assert db.query(Estimate).count() == 0


def test_scene_regeneration_and_export_claim_are_serialized(client, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from fastapi import BackgroundTasks
    import api.routes
    from api.routes import generate_scene_image, start_video
    from schemas.schemas import VideoRequest

    client, sessions, _ = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "target_minutes": 1, "max_budget": 5, "max_wait_minutes": 20,
    }).json()["project_id"]
    client.post(f"/api/v1/projects/{project_id}/analyze")
    client.post(f"/api/v1/projects/{project_id}/select-plan", json={"plan": "economy"})
    scene_id = client.get(f"/api/v1/projects/{project_id}/scenes").json()[0]["id"]
    generating = Event()
    release = Event()
    claiming = Event()
    original = FixtureAIProvider.generate_scene_image

    def blocked_generate(self, *args, **kwargs):
        generating.set()
        assert release.wait(5)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(FixtureAIProvider, "generate_scene_image", blocked_generate)
    with sessions() as db:
        from models.models import Project
        for character in db.get(Project,project_id).characters:
            character.approved = True
        db.commit()

    def regenerate():
        with sessions() as db:
            generate_scene_image(scene_id, db, regenerate=True)

    def claim():
        with sessions() as db:
            claiming.set()
            return start_video(project_id, VideoRequest(plan="economy"), BackgroundTasks(), db)

    with ThreadPoolExecutor(max_workers=2) as pool:
        scene_future = pool.submit(regenerate)
        try:
            assert generating.wait(5)
            job_future = pool.submit(claim)
            assert claiming.wait(5)
            assert not job_future.done()
        finally:
            release.set()
        scene_future.result(timeout=10)
        assert job_future.result(timeout=10)["status"] == "queued"
    assert client.get(f"/api/v1/projects/{project_id}/scenes").json()[0]["image_path"] is not None


@pytest.mark.parametrize("failure", ["estimation", "commit"])
def test_failed_refresh_preserves_published_media(client, monkeypatch, failure):
    from models.models import Project
    from repositories.project_repository import ProjectRepository
    from services.estimation_service import EstimationService

    client, sessions, storage = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "target_minutes": 1, "max_budget": 5, "max_wait_minutes": 20,
    }).json()["project_id"]
    client.post(f"/api/v1/projects/{project_id}/analyze")
    client.post(f"/api/v1/projects/{project_id}/select-plan", json={"plan": "economy"})
    story = client.get(f"/api/v1/projects/{project_id}/story").json()
    character_id, scene_id = story["characters"][0]["id"], story["scenes"][0]["id"]
    confirmed_post(client,f"/api/v1/characters/{character_id}/portrait")
    confirmed_post(client,f"/api/v1/scenes/{scene_id}/generate")
    directory = storage / "projects" / str(project_id)
    paths = [directory / f"character-{character_id}.png", directory / f"scene-{scene_id}.png", directory / "video.mp4"]
    paths[-1].write_bytes(b"old video")
    with sessions() as db:
        db.get(Project, project_id).video_path = str(paths[-1])
        db.commit()
    before = [path.read_bytes() for path in paths]
    original_story = client.get(f"/api/v1/projects/{project_id}/story").json()

    def fail(*args, **kwargs):
        raise RuntimeError(f"{failure} failed")

    if failure == "estimation":
        monkeypatch.setattr(EstimationService, "calculate", fail)
    else:
        monkeypatch.setattr(ProjectRepository, "save", fail)
    with pytest.raises(RuntimeError, match=f"{failure} failed"):
        client.post(f"/api/v1/projects/{project_id}/story/regenerate")
    assert [path.read_bytes() for path in paths] == before
    assert client.get(f"/api/v1/projects/{project_id}/story").json() == original_story
    assert client.get(f"/api/v1/projects/{project_id}").json()["video_url"] is not None


def test_successful_refresh_removes_obsolete_media(client):
    from models.models import Project

    client, sessions, storage = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "max_budget": 5, "max_wait_minutes": 20,
    }).json()["project_id"]
    client.post(f"/api/v1/projects/{project_id}/analyze")
    client.post(f"/api/v1/projects/{project_id}/select-plan", json={"plan": "economy"})
    story = client.get(f"/api/v1/projects/{project_id}/story").json()
    character_id, scene_id = story["characters"][0]["id"], story["scenes"][0]["id"]
    confirmed_post(client,f"/api/v1/characters/{character_id}/portrait")
    confirmed_post(client,f"/api/v1/scenes/{scene_id}/generate")
    directory = storage / "projects" / str(project_id)
    paths = [directory / f"character-{character_id}.png", directory / f"scene-{scene_id}.png", directory / "video.mp4"]
    paths[-1].write_bytes(b"old video")
    with sessions() as db:
        db.get(Project, project_id).video_path = str(paths[-1])
        db.commit()
    assert all(path.exists() for path in paths)
    assert client.post(f"/api/v1/projects/{project_id}/story/regenerate").status_code == 200
    assert not any(path.exists() for path in paths)


def test_cleanup_preserves_new_media_published_after_refresh_commit(client, monkeypatch):
    from repositories.project_repository import ProjectRepository
    from services.project_service import ProjectService

    client, sessions, storage = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "max_budget": 5, "max_wait_minutes": 20,
    }).json()["project_id"]
    client.post(f"/api/v1/projects/{project_id}/analyze")
    client.post(f"/api/v1/projects/{project_id}/select-plan", json={"plan": "economy"})
    old_scene = client.get(f"/api/v1/projects/{project_id}/scenes").json()[0]["id"]
    confirmed_post(client,f"/api/v1/scenes/{old_scene}/generate")
    old_path = storage / "projects" / str(project_id) / f"scene-{old_scene}.png"
    original_cleanup = ProjectService._remove_obsolete_media

    def publish_then_cleanup(service, project_id, obsolete):
        with sessions() as db:
            project = ProjectRepository(db).get_project(project_id)
            scene = project.scenes[0]
            scene.id = old_scene
            old_path.write_bytes(b"newly published")
            scene.image_path = f"/storage/projects/{project_id}/{old_path.name}"
            db.commit()
        original_cleanup(service, project_id, obsolete)

    monkeypatch.setattr(ProjectService, "_remove_obsolete_media", publish_then_cleanup)
    assert client.post(f"/api/v1/projects/{project_id}/story/regenerate").status_code == 200
    assert old_path.read_bytes() == b"newly published"


def test_cleanup_skips_files_when_export_starts_after_commit(client, monkeypatch, caplog):
    from models.models import Job
    from services.project_service import ProjectService

    client, sessions, storage = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "max_budget": 5, "max_wait_minutes": 20,
    }).json()["project_id"]
    client.post(f"/api/v1/projects/{project_id}/analyze")
    client.post(f"/api/v1/projects/{project_id}/select-plan", json={"plan": "economy"})
    scene_id = client.get(f"/api/v1/projects/{project_id}/scenes").json()[0]["id"]
    confirmed_post(client,f"/api/v1/scenes/{scene_id}/generate")
    old_path = storage / "projects" / str(project_id) / f"scene-{scene_id}.png"
    assert old_path.exists()
    original_cleanup = ProjectService._remove_obsolete_media

    def claim_then_cleanup(service, project_id, obsolete):
        with sessions() as db:
            db.add(Job(id="new-export", project_id=project_id, status="queued"))
            db.commit()
        original_cleanup(service, project_id, obsolete)

    monkeypatch.setattr(ProjectService, "_remove_obsolete_media", claim_then_cleanup)
    with caplog.at_level("INFO", logger="services.project_service"):
        assert client.post(f"/api/v1/projects/{project_id}/story/regenerate").status_code == 200
    assert old_path.exists()
    assert "Skipping obsolete media cleanup" in caplog.text


def test_cleanup_failure_is_logged_after_refresh(client, monkeypatch, caplog):
    client, _, storage = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "max_budget": 5, "max_wait_minutes": 20,
    }).json()["project_id"]
    client.post(f"/api/v1/projects/{project_id}/analyze")
    client.post(f"/api/v1/projects/{project_id}/select-plan", json={"plan": "economy"})
    scene_id = client.get(f"/api/v1/projects/{project_id}/scenes").json()[0]["id"]
    confirmed_post(client,f"/api/v1/scenes/{scene_id}/generate")
    old_path = storage / "projects" / str(project_id) / f"scene-{scene_id}.png"
    unlink = Path.unlink

    def deny(self, *args, **kwargs):
        if self == old_path:
            raise PermissionError("locked file")
        return unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", deny)
    with caplog.at_level("ERROR", logger="services.project_service"):
        assert client.post(f"/api/v1/projects/{project_id}/story/regenerate").status_code == 200
    assert old_path.exists()
    assert "Could not remove obsolete project media" in caplog.text


def test_portrait_generation_is_serialized_with_story_edit(client, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from api.routes import generate_portrait
    from repositories.project_repository import ProjectRepository
    from services.project_service import ProjectService
    from services.story_service import StoryService
    from schemas.schemas import StoryUpdate

    client, sessions, _ = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "max_budget": 5, "max_wait_minutes": 20,
    }).json()["project_id"]
    client.post(f"/api/v1/projects/{project_id}/analyze")
    client.post(f"/api/v1/projects/{project_id}/select-plan", json={"plan": "economy"})
    story = client.get(f"/api/v1/projects/{project_id}/story").json()
    character_id = story["characters"][0]["id"]
    story["characters"][0]["description"] = "New description"
    payload = StoryUpdate(**story)
    rendering, release, editing = Event(), Event(), Event()
    original = FixtureAIProvider.generate_character_portrait

    def render(self, *args, **kwargs):
        rendering.set()
        assert release.wait(5)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(FixtureAIProvider, "generate_character_portrait", render)
    with sessions() as db:
        from models.models import Project
        db.get(Project,project_id).story_approved = True
        db.commit()

    def portrait():
        with sessions() as db:
            return generate_portrait(character_id, db)

    def edit():
        with sessions() as db:
            editing.set()
            repository = ProjectRepository(db)
            repository.begin_write()
            project = ProjectService(repository).get(project_id)
            StoryService(repository).update(
                project,
                payload.title,
                payload.summary,
                payload.genre,
                payload.target_audience,
                payload.three_act_structure,
                payload.characters,
                payload.scenes,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        portrait_future = pool.submit(portrait)
        try:
            assert rendering.wait(5)
            edit_future = pool.submit(edit)
            assert editing.wait(5)
            assert not edit_future.done()
        finally:
            release.set()
        assert portrait_future.result(timeout=10)["status"] == "completed"
        edit_future.result(timeout=10)
    character = client.get(f"/api/v1/projects/{project_id}/characters").json()[0]
    assert character["description"] == "New description"
    assert character["image_path"] is None


def test_project_listing_loads_estimates_without_n_plus_one(client):
    from sqlalchemy import event

    client, sessions, _ = client
    for index in range(5):
        project_id = client.post("/api/v1/projects", json={
            "prompt": f"A gardener finds doorway number {index}.",
            "max_budget": 5, "max_wait_minutes": 20,
        }).json()["project_id"]
        client.post(f"/api/v1/projects/{project_id}/analyze")
        client.post(f"/api/v1/projects/{project_id}/select-plan", json={"plan": "economy"})
    statements = []
    engine = sessions.kw["bind"]

    def count(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", count)
    try:
        response = client.get("/api/v1/projects")
    finally:
        event.remove(engine, "before_cursor_execute", count)
    assert response.status_code == 200
    assert len(response.json()) == 5
    assert all(project["estimated_cost"] is not None for project in response.json())
    assert len(statements) == 2
