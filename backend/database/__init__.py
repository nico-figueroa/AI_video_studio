"""SQLite database engine, metadata, and request-scoped sessions."""

from collections.abc import Generator
from contextlib import closing
from pathlib import Path
import shutil
import sqlite3
import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
DATABASE_URL = f"sqlite:///{(STORAGE_DIR / 'studio.db').as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def migrate_legacy_storage() -> None:
    legacy = BASE_DIR / "database" / "storage"
    if STORAGE_DIR.exists():
        if (legacy / "studio.db").is_file() and not (STORAGE_DIR / "studio.db").is_file():
            raise RuntimeError(
                f"Legacy data exists at {legacy}, but {STORAGE_DIR} already exists without a database. "
                "Move or back up that directory before starting the migration."
            )
        return
    if not (legacy / "studio.db").is_file():
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        return

    with tempfile.TemporaryDirectory(prefix="studio-migration-", dir=BASE_DIR) as temporary:
        destination = Path(temporary) / "storage"
        shutil.copytree(legacy, destination, ignore=shutil.ignore_patterns("studio.db", "studio.db-wal", "studio.db-shm"))
        with closing(sqlite3.connect(legacy / "studio.db")) as source, closing(sqlite3.connect(destination / "studio.db")) as target:
            source.backup(target)
            for table, column in (("projects", "video_path"), ("generated_assets", "file_path")):
                rows = target.execute(f"SELECT id, {column} FROM {table} WHERE {column} IS NOT NULL").fetchall()
                for row_id, value in rows:
                    try:
                        relative = Path(value).relative_to(legacy)
                    except ValueError:
                        continue
                    target.execute(f"UPDATE {table} SET {column} = ? WHERE id = ?", (str(STORAGE_DIR / relative), row_id))
            target.commit()
        destination.rename(STORAGE_DIR)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
