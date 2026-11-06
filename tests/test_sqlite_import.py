import sqlite3
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from database import run_migrations
from scripts.migrate_sqlite_to_postgres import migrate
from scripts.migrate_sqlite_to_postgres import _rewrite_asset_path


def test_sqlite_import_preserves_ids_and_rewrites_project_assets(tmp_path):
    legacy_storage = tmp_path / "legacy" / "storage"
    legacy_media = legacy_storage / "projects" / "8" / "final-video.mp4"
    legacy_media.parent.mkdir(parents=True)
    legacy_media.write_bytes(b"legacy media")
    sqlite_path = legacy_storage / "studio.db"
    with sqlite3.connect(sqlite_path) as source:
        source.execute(
            "CREATE TABLE projects (id INTEGER PRIMARY KEY, title TEXT, prompt TEXT, video_path TEXT)"
        )
        source.execute(
            "INSERT INTO projects VALUES (?, ?, ?, ?)",
            (8, "Legacy project", "A migrated project idea.", str(legacy_media)),
        )
        source.commit()

    target_path = tmp_path / "target.db"
    target_engine = create_engine(f"sqlite:///{target_path.as_posix()}")
    storage_dir = tmp_path / "new-storage"
    storage_dir.mkdir()
    copied_media = storage_dir / "projects" / "8" / "final-video.mp4"
    copied_media.parent.mkdir(parents=True)
    copied_media.write_bytes(legacy_media.read_bytes())
    try:
        run_migrations(target_engine)
    finally:
        target_engine.dispose()

    migrate(
        sqlite_path,
        f"sqlite:///{target_path.as_posix()}",
        storage_dir,
    )

    with create_engine(f"sqlite:///{target_path.as_posix()}").connect() as target:
        row = target.execute(text(
            "SELECT id, title, video_path, estimated_spend FROM projects"
        )).one()
    assert row.id == 8
    assert row.title == "Legacy project"
    assert Path(row.video_path) == copied_media
    assert row.estimated_spend == 0
    assert sqlite_path.is_file()
    assert legacy_media.read_bytes() == b"legacy media"


def test_sqlite_import_fails_when_destination_tables_are_missing(tmp_path):
    sqlite_path = tmp_path / "source.db"
    with sqlite3.connect(sqlite_path) as source:
        source.execute("CREATE TABLE projects (id INTEGER PRIMARY KEY, title TEXT)")
        source.execute("INSERT INTO projects VALUES (1, 'A project')")

    target_path = tmp_path / "target.db"
    with pytest.raises(RuntimeError, match="missing required tables: projects"):
        migrate(sqlite_path, f"sqlite:///{target_path.as_posix()}", tmp_path / "storage")


def test_sqlite_import_preserves_public_storage_urls(tmp_path):
    url = "/storage/projects/8/scene-1.png"
    assert _rewrite_asset_path(url, tmp_path / "storage", tmp_path) == url
