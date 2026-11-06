import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi.testclient import TestClient

from main import app


def test_health_and_project_planning_flow(tmp_path, monkeypatch):
    from database import Base, get_db
    import api.routes
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    test_engine = create_engine(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    TestingSession = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(api.routes, "SessionLocal", TestingSession)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
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
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(test_engine)
