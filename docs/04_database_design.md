# Database Design and Migration Plan

## Database Technology

PostgreSQL is the runtime database. SQLAlchemy 2.x models are in `backend/models/`; Alembic migrations are in `backend/migrations/`. `DATABASE_URL` uses the SQLAlchemy `postgresql+psycopg://` driver. Application startup upgrades to Alembic `head`; do not use `Base.metadata.create_all` in application code.

## Phase 2 Schema

### `projects`

`id` (integer primary key), `title`, `prompt`, `story_summary`, `genre`, `target_audience`, `three_act_structure` (JSON), `status`, `target_minutes`, `max_budget`, `max_wait_minutes`, `selected_plan` (legacy Phase 1), `video_path` (legacy Phase 1), `actual_cost` (legacy local-export metric), `estimated_spend` (reserved AI planning estimate), `created_at`.

### `characters`

`id`, `project_id` (FK), `name`, `description`, `role`, `personality`, `appearance`, `motivations`, `relationships`, `portrait_prompt`, `image_path`, `approved`.

### `scenes`

`id`, `project_id` (FK), `scene_number`, `title`, `description`, `visual_description`, `image_prompt`, `estimated_duration` (seconds), `image_path`, `status`, `approved`. `(project_id, scene_number)` is unique.

### `estimates`

Legacy Phase 1 plan comparison fields (`project_id`, plan, estimated cost/time, resolution, quality, storage, GPU estimate). Phase 2 per-operation estimates are calculated from the selected model and configured planning rates and returned before execution; they are not provider quotes.

### `generated_assets`

`id`, `project_id` (FK), `asset_type`, `file_path`, `created_at`. Paths identify files in local project storage.

### `jobs`

`id` (UUID string), `project_id` (FK), `status`, `progress`, `current_stage`, `error`, `started_at`, `completed_at`. A partial unique index allows at most one queued/running legacy export per project.

### `ai_configuration`

Singleton row (`id = 1`) with `provider`, `model`, `image_model`, `default_budget`, `default_wait_minutes`, and `updated_at`. The OpenAI API key is intentionally not stored here.

## Migration Inventory

- `0001_phase2` creates the PostgreSQL-compatible Phase 2 schema and indexes. It is also exercised against SQLite in tests only.
- Subsequent model/schema changes require a new Alembic revision. Never rewrite a migration already deployed.
- Legacy media is copied from `backend/database/storage/projects` into `backend/storage/projects` at startup, without copying or deleting the old SQLite database.
- [`.env.example`](../.env.example) contains the connection and provider settings template.

## SQLite to PostgreSQL Runbook

1. Stop the Phase 1 backend and take a verified backup of `backend/database/storage/studio.db` and its `projects` directory. Do not delete the source.
2. Create an empty PostgreSQL database (the database itself must exist before Alembic runs) and set `DATABASE_URL` in the root `.env`. For a local database named `ai_video_studio`, run `psql -U postgres -h localhost -p 5432 -d postgres -c "CREATE DATABASE ai_video_studio;"`; use the role from `DATABASE_URL` as the owner or grant it access.
3. Install backend requirements, then from `backend` run `alembic upgrade head` (or start the app once to apply migrations).
4. Ensure legacy project media is copied to `backend/storage/projects`, preserving project subdirectories. Startup performs a non-destructive copy.
5. From the repository root run `python scripts\migrate_sqlite_to_postgres.py --sqlite backend\database\storage\studio.db`. The script copies shared table columns in FK order, rewrites known local asset roots, preserves IDs, resets PostgreSQL ID sequences, and refuses to write into non-empty target tables. `DATABASE_URL` supplies the target.
6. Compare row counts for projects, characters, scenes, estimates, generated assets, and jobs. Open representative projects and verify every referenced asset before directing traffic to PostgreSQL.
7. Keep the SQLite database and media backup read-only until verification and rollback windows expire. Roll back by stopping the service and restoring the previous release/configuration; do not reverse-import PostgreSQL writes into SQLite.

The import script runs in one PostgreSQL transaction; a failed import rolls back. It does not delete SQLite rows or media. It intentionally does not copy an old AI key or any environment secrets.
```