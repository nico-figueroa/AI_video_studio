"""Opt-in integration test using an isolated schema, never the application's tables."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from test_production import ProductionProvider
from database import BASE_DIR, Base, engine, run_migrations
from models.models import Project, Video
from repositories.production_repository import ProductionRepository
from schemas.production import NarrationRequest, ProductionApproval, RenderRequest
from services.narration_service import NarrationService
from services.project_service import ProjectService
from services.render_service import RenderService
from services.image_service import public_asset_url


@pytest.mark.skipif(os.getenv("STUDIO_TEST_POSTGRES") != "1", reason="Set STUDIO_TEST_POSTGRES=1 for isolated PostgreSQL integration.")
def test_postgresql_upgrade_and_production_roundtrip(tmp_path, monkeypatch):
    import services.image_service
    import services.narration_service

    schema = "phase3_test_" + uuid4().hex
    isolated = create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    provider = ProductionProvider()
    monkeypatch.setattr(services.image_service, "STORAGE_DIR", tmp_path)
    monkeypatch.setattr(services.narration_service, "create_ai_provider", lambda configuration: provider)
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        configuration = Config(str(BASE_DIR / "alembic.ini"))
        configuration.set_main_option("script_location", str(BASE_DIR / "migrations"))
        with isolated.begin() as connection:
            configuration.attributes["connection"] = connection
            command.upgrade(configuration, "0001_phase2")
            connection.execute(text("INSERT INTO projects (prompt) VALUES ('A preserved Phase 2 project')"))
        run_migrations(isolated)
        assert {"narrations", "render_jobs", "videos"}.issubset(inspect(isolated).get_table_names())
        with isolated.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection),Base.metadata)==[]
        sessions = sessionmaker(bind=isolated, autoflush=False, expire_on_commit=False)
        with sessions() as db:
            assert db.query(Project).count() == 1
            preserved = db.query(Project).one()
            assert not preserved.story_approved and preserved.input_manifest=={} and preserved.review_overrides==[]
            repository = ProductionRepository(db)
            project = ProjectService(repository).create(
                prompt="A diver discovers a city under the ocean.", max_budget=10,
            )
            project_id = project.id
            ProjectService(repository).analyze(project_id, provider=provider)
            project = ProjectService(repository).get(project_id)
            project.story_approved = True
            for character in project.characters:
                character.approved = True
            for scene in project.scenes:
                path = tmp_path / "projects" / str(project_id) / f"scene-{scene.id}.png"
                provider.generate_scene_image(scene.image_prompt, path)
                scene.image_path = public_asset_url(path)
                scene.approved = True
                scene.estimated_duration = 1
            repository.save()
            narration = NarrationService(repository)
            estimate = narration.get(project_id).narration_estimate
            db.rollback()
            narration.generate(project_id, NarrationRequest(approved=True, estimate_id=estimate.estimate_id))
            estimate = narration.get(project_id).audio_estimate
            db.rollback()
            narration.generate_audio(project_id, ProductionApproval(approved=True, estimate_id=estimate.estimate_id))
            render = RenderService(repository)
            estimate = render.estimate(project_id, "still_images")
            db.rollback()
            status = render.start(project_id, RenderRequest(approved=True, estimate_id=estimate.estimate_id, mode="still_images"))
            db.rollback()
            render.run(status.job_id)
            assert render.status(project_id).status == "completed"
            video = db.query(Video).one()
            assert Path(video.file_path).is_file()
            assert video.duration_seconds == 4
        # A second upgrade is idempotent and keeps Phase 2 data.
        run_migrations(isolated)
        with isolated.connect() as connection:
            assert connection.execute(text("select count(*) from projects")).scalar() == 2
    finally:
        isolated.dispose()
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
