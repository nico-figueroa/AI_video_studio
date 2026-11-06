import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    from database import get_db
    import api.routes
    import main
    import services.image_service
    import services.story_service
    import services.video_service
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    storage = tmp_path / "storage"
    (storage / "projects").mkdir(parents=True)
    for module in (main, api.routes, services.image_service, services.story_service, services.video_service):
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
    image_without_plan = client.post(
        f"/api/v1/scenes/{story['scenes'][0]['id']}/generate"
    )
    assert image_without_plan.status_code == 409
    assert client.post(
        f"/api/v1/projects/{project_id}/select-plan",
        json={"plan": "economy"},
    ).status_code == 200
    assert client.post(
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
            "max_wait_minutes": 2,
        },
    ).json()["project_id"]
    client.post(f"/api/v1/projects/{constrained}/analyze")
    too_slow = client.post(
        f"/api/v1/projects/{constrained}/select-plan",
        json={"plan": "economy"},
    )
    assert too_slow.status_code == 422


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


def test_portrait_regeneration_requires_reapproval(client):
    client, _, _ = client
    project_id = client.post("/api/v1/projects", json={
        "prompt": "A gardener finds a doorway beneath a glasshouse.",
        "target_minutes": 1, "max_budget": 5, "max_wait_minutes": 20,
    }).json()["project_id"]
    client.post(f"/api/v1/projects/{project_id}/analyze")
    client.post(f"/api/v1/projects/{project_id}/select-plan", json={"plan": "economy"})
    character_id = client.get(f"/api/v1/projects/{project_id}/characters").json()[0]["id"]
    client.put(f"/api/v1/characters/{character_id}", json={"approved": True})
    assert client.post(f"/api/v1/characters/{character_id}/portrait").status_code == 200
    assert not client.get(f"/api/v1/projects/{project_id}/characters").json()[0]["approved"]


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
    import sqlite3
    from contextlib import closing
    import database

    legacy = tmp_path / "database" / "storage"
    old_video = legacy / "projects" / "1" / "final-video.mp4"
    old_video.parent.mkdir(parents=True)
    old_video.write_bytes(b"old video")
    with closing(sqlite3.connect(legacy / "studio.db")) as db:
        db.execute("CREATE TABLE projects (id INTEGER PRIMARY KEY, video_path TEXT)")
        db.execute("CREATE TABLE generated_assets (id INTEGER PRIMARY KEY, file_path TEXT)")
        db.execute("INSERT INTO projects VALUES (1, ?)", (str(old_video),))
        db.execute("INSERT INTO generated_assets VALUES (1, ?)", (str(old_video),))
        db.commit()
    monkeypatch.setattr(database, "BASE_DIR", tmp_path)
    monkeypatch.setattr(database, "STORAGE_DIR", tmp_path / "storage")
    database.migrate_legacy_storage()
    new_video = tmp_path / "storage" / "projects" / "1" / "final-video.mp4"
    assert new_video.read_bytes() == old_video.read_bytes()
    with closing(sqlite3.connect(tmp_path / "storage" / "studio.db")) as db:
        assert db.execute("SELECT video_path FROM projects").fetchone()[0] == str(new_video)
        assert db.execute("SELECT file_path FROM generated_assets").fetchone()[0] == str(new_video)
    assert old_video.exists()
