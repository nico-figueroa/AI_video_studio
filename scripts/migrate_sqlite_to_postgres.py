import argparse
import os
from pathlib import Path

from sqlalchemy import Integer, MetaData, create_engine, func, insert, select
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


TABLE_ORDER = (
    "projects",
    "ai_configuration",
    "characters",
    "scenes",
    "estimates",
    "generated_assets",
    "jobs",
)


def migrate(sqlite_path: Path, database_url: str, storage_dir: Path) -> None:
    if not sqlite_path.is_file():
        raise FileNotFoundError(f"SQLite source database does not exist: {sqlite_path}")
    source_engine = create_engine(f"sqlite:///{sqlite_path.resolve().as_posix()}")
    target_engine = create_engine(database_url, pool_pre_ping=True)
    source_metadata = MetaData()
    target_metadata = MetaData()
    source_metadata.reflect(bind=source_engine)
    target_metadata.reflect(bind=target_engine)
    tables = [
        name for name in TABLE_ORDER
        if name in source_metadata.tables and name in target_metadata.tables
    ]

    try:
        with source_engine.connect() as source, target_engine.begin() as target:
            for name in tables:
                table = target_metadata.tables[name]
                if target.scalar(select(func.count()).select_from(table)):
                    raise RuntimeError(
                        f"Target table '{name}' is not empty. Refusing to duplicate source rows."
                    )

            for name in tables:
                source_table = source_metadata.tables[name]
                target_table = target_metadata.tables[name]
                source_rows = source.execute(select(source_table)).mappings()
                target_columns = set(target_table.c.keys())
                common_columns = target_columns & set(source_table.c.keys())
                batch = []
                for source_row in source_rows:
                    row = {
                        column: source_row[column]
                        for column in common_columns
                    }
                    for column in ("video_path", "image_path", "file_path"):
                        value = row.get(column)
                        if value:
                            row[column] = _rewrite_asset_path(
                                value, storage_dir, sqlite_path.parent
                            )
                    batch.append(row)
                    if len(batch) == 500:
                        target.execute(insert(target_table), batch)
                        batch.clear()
                if batch:
                    target.execute(insert(target_table), batch)

            if target.dialect.name == "postgresql":
                for name in tables:
                    table = target_metadata.tables[name]
                    if "id" not in table.c or not isinstance(table.c.id.type, Integer):
                        continue
                    target.execute(
                        select(
                            func.setval(
                                func.pg_get_serial_sequence(name, "id"),
                                func.coalesce(select(func.max(table.c.id)).scalar_subquery(), 1),
                                select(func.max(table.c.id)).scalar_subquery().is_not(None),
                            )
                        )
                    )
    finally:
        source_engine.dispose()
        target_engine.dispose()


def _rewrite_asset_path(value: str, storage_dir: Path, sqlite_directory: Path) -> str:
    path = Path(value)
    roots = (storage_dir, sqlite_directory)
    if not path.is_absolute() and "projects" in path.parts:
        relative = Path(*path.parts[path.parts.index("projects"):])
        return str(storage_dir / relative)
    for root in roots:
        try:
            relative = path.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        if "projects" in relative.parts:
            return str(storage_dir / relative)
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy existing MVP rows from SQLite into an already-migrated PostgreSQL database."
    )
    parser.add_argument("--sqlite", type=Path, required=True, help="Path to the SQLite MVP database.")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="Target PostgreSQL SQLAlchemy URL, such as postgresql+psycopg://...",
    )
    parser.add_argument(
        "--storage-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "backend" / "storage",
        help="Destination for the already-copied local project assets.",
    )
    args = parser.parse_args()
    if not args.database_url:
        parser.error("Provide --database-url or set DATABASE_URL.")
    migrate(args.sqlite, args.database_url, args.storage_dir.resolve())
    print("SQLite rows copied to PostgreSQL. Verify the counts before retiring the source database.")


if __name__ == "__main__":
    main()
