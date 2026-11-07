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

- `0005_workflow` changes `projects.target_minutes` to floating-point storage so integer second targets are not rounded to minutes. Existing minute targets are preserved; API/model `target_seconds` is derived. Adds project JSON `generation_approval` for bounded prompt/model/rate/capability-bound automatic stage consent, and job `operation`/JSON `snapshot` for missing-asset IDs, completion checkpoints and reserved estimates. The existing active-project index serializes image and motion batches alongside legacy jobs. Downgrade rounds fractional minutes upward.
- Confirmed project restart/deletion explicitly removes dependent rows in FK order. Video deletion removes exports/render checkpoints only. Media moves into private pending-deletion storage before the transaction and is restored on transaction failure. Restart keeps historical spending but resets all generation/review/import state.
- Render snapshots now persist an explicit source mode. `local_animation` requires current approved clips for every scene; `still_images` never dispatches the local model. Video responses derive source counts from the saved snapshot, not current project state.

- `0004_animation` adds `animation_jobs`: UUID, project/scene FK, global GPU slot,
  queued/running/completed/failed status, progress, source hash, input snapshot,
  result metadata, clip path, explicit approval, error and creation timestamp.
  A partial unique active-slot index prevents simultaneous local GPU jobs.
  Scene deletion cascades its job metadata; media is retained. It also adds
  project `narrative_analysis` JSON, scene `beat_number` (legacy default 1), and
  character `facial_features`. Existing rows are retained. Downgrade drops only
  these additions, not model files or project media. Back up before migrating.

- `0003_quality` extends existing rows non-destructively:
  - `projects`: `story_approved`, JSON `input_manifest` (classification/provenance/source transcript/local audio metadata), JSON `narration_arc`, JSON `review_overrides` (last 100 explicit stage/token/time acknowledgements).
  - `characters`: clothing, age, distinctive traits, negative prompt, JSON immutable approved `reference_image_paths`, JSON `generation_context`.
  - `scenes`: JSON `motion_plan` (camera/focus/transition/pacing and deferred animation/movement prompts), JSON `generation_context` (story/character hashes/reference count).
  - `narrations`: `transition_text`; `source_hash` now fingerprints the whole narrative revision plus scene ID.
  - Defaults preserve old Phase 2/3 rows but do not claim they have been reviewed or generated with new continuity context. Old narration fingerprints become stale and require regeneration.
  - Full stories/scripts and original uploaded audio remain preserved; only safe public input metadata is returned by input endpoints. Raw source, normalized audio, imported images and immutable portrait references stay local. Keep them in media backups.
  - Upgrade with `alembic upgrade head`. Downgrading `0003_quality` removes these columns, not media or original production tables; back up first.

- `0002_phase3` adds production tables without rewriting Phase 2:
  - `narrations`: project FK, unique scene FK (cascade on deletion), text, scene-source hash, recommended seconds, provider/text model, nullable local audio path/measured seconds/speech model/voice, created timestamp.
  - `render_jobs`: UUID, project FK, status/progress/stage/error, timeline hash, JSON timeline/estimate snapshot, JSON completed scene IDs, accumulated execution seconds, created/started/completed timestamps. A partial unique index allows one queued/running render per project.
  - `videos`: project FK, unique render-job FK, published MP4 path, video/audio seconds, file size, render execution seconds, local estimated cost, created timestamp.
- Timeline order/duration reuse `scenes.scene_number` and `scenes.estimated_duration`; a separate timeline table is not required. Render snapshots retain the exact approved order, duration, narration, and asset links for recovery.
- New WAVs and MP4s remain in `backend/storage/projects/{project_id}`; checkpoints in `render-{job_id}`. Database metadata is PostgreSQL only. Media files are not binary database columns.
- Story regeneration replaces scenes and removes their associated narration rows through the FK/ORM cascade. Published-video and job records remain historical; local narration/audio/checkpoints are retained, not automatically garbage-collected.
- Run `alembic upgrade head` before serving the new APIs (startup also does this). Back up PostgreSQL and local media first. Downgrade `0002_phase3` removes only the three production tables and their metadata; it does not delete media or Phase 2 rows.

- `0001_phase2` creates the PostgreSQL-compatible Phase 2 schema and indexes. It is also exercised against SQLite in tests only.
- Subsequent model/schema changes require a new Alembic revision. Never rewrite a migration already deployed.
- Legacy media is copied from `backend/database/storage/projects` into `backend/storage/projects` at startup, without copying or deleting the old SQLite database.
- [`.env.example`](../.env.example) contains the connection and provider settings template.

## SQLite to PostgreSQL Runbook

1. Stop the backend and take a verified backup of the active SQLite database at `backend/storage/studio.db` and the `backend/storage/projects` directory. Do not delete the source. Only for installations that never completed the prior migration, if the active database does not exist, use `backend/database/storage/studio.db` as the fallback database and its `backend/database/storage/projects` directory.
2. Create an empty PostgreSQL database (the database itself must exist before Alembic runs) and set `DATABASE_URL` in the root `.env`. For a local database named `ai_video_studio`, run `psql -U postgres -h localhost -p 5432 -d postgres -c "CREATE DATABASE ai_video_studio;"`; use the role from `DATABASE_URL` as the owner or grant it access.
3. Install backend requirements, then from `backend` run `alembic upgrade head` (or start the app once to apply migrations).
4. Ensure legacy project media is copied to `backend/storage/projects`, preserving project subdirectories. Startup performs a non-destructive copy.
5. From the repository root run `python scripts\migrate_sqlite_to_postgres.py --sqlite backend\storage\studio.db`. For an installation that never completed the prior migration and has no `backend/storage/studio.db`, use `python scripts\migrate_sqlite_to_postgres.py --sqlite backend\database\storage\studio.db` instead. The script copies shared table columns in FK order, rewrites known local asset roots, preserves IDs, resets PostgreSQL ID sequences, and refuses to write into non-empty target tables. `DATABASE_URL` supplies the target.
6. Compare row counts for projects, characters, scenes, estimates, generated assets, and jobs. Open representative projects and verify every referenced asset before directing traffic to PostgreSQL.
7. Keep the SQLite database and media backup read-only until verification and rollback windows expire. Roll back by stopping the service and restoring the previous release/configuration; do not reverse-import PostgreSQL writes into SQLite.

The import script runs in one PostgreSQL transaction; a failed import rolls back. It does not delete SQLite rows or media. It intentionally does not copy an old AI key or any environment secrets.
```