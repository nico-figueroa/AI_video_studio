"""PostgreSQL database engine, Alembic migrations, and request-scoped sessions."""

from collections.abc import Generator
from pathlib import Path
import os
import shutil

from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
load_dotenv(BASE_DIR.parent / ".env")


def _database_url() -> str:
    url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/ai_video_studio",
    )
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


DATABASE_URL = _database_url()
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def migrate_legacy_storage() -> None:
    """Copy legacy project media, but keep the SQLite database as a backup only."""
    legacy = BASE_DIR / "database" / "storage"
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    marker = STORAGE_DIR / ".legacy-media-imported"
    if marker.exists():
        return
    legacy_projects = legacy / "projects"
    if not legacy_projects.is_dir():
        return
    for source in legacy_projects.rglob("*"):
        if not source.is_file():
            continue
        destination = STORAGE_DIR / source.relative_to(legacy)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(source, destination)
    marker.write_text("Legacy media copied. Do not replay after project deletion or restart.\n", encoding="utf-8")


def run_migrations(database_engine: Engine = engine) -> None:
    config = Config(str(BASE_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BASE_DIR / "migrations"))
    with database_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
