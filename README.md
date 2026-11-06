# AI Video Studio

Phase 2 turns the Phase 1 workflow prototype into an AI-powered story-planning studio. It generates structured story, character, and scene bibles, then individual portraits and scene images. Before each provider call, the app displays estimated cost, duration, model usage, and API-call count.

## Phase 2 Scope

- PostgreSQL persistence with SQLAlchemy and Alembic.
- OpenAI text and image generation behind the `AIProvider` interface.
- AI configuration at `/settings/ai`.
- Story Bible, Character Bible, Scene Plan, portrait, and scene image routes.
- Local project-scoped image storage with paths in PostgreSQL.
- Estimate-first UX, budget reservations, progress indicators, and explicit error reporting.

Animation, voice, music, and new final-video generation are out of scope. The existing Phase 1 local MP4 export remains legacy functionality and is not extended.

## Configure

1. Copy `.env.example` to `.env`.
2. Set `DATABASE_URL` to a PostgreSQL database using the `postgresql+psycopg://` driver.
3. Set `OPENAI_API_KEY` on the backend. The key is never saved in PostgreSQL or sent to the frontend.
4. Review the planning estimate rates against current OpenAI pricing. The estimates are not provider quotes; actual invoice totals are not reported by this app.

Additional detail is in [environment configuration](./docs/.env_specification.md).

The PostgreSQL server must be running, and the database named in `DATABASE_URL` must already exist. Alembic creates the tables, not the PostgreSQL database. For the default local database name, create it once from PowerShell:

```powershell
psql -U postgres -h localhost -p 5432 -d postgres -c "CREATE DATABASE ai_video_studio;"
```

Use the PostgreSQL role from your `DATABASE_URL` if it is not `postgres`; that role must own the database or have the required privileges. Skip the create command if the database already exists.

## Run Locally

Use Python 3.10+ and Node.js 20+. Run backend and frontend in separate terminals.

### Backend (PowerShell)

Run these commands from the repository root:

```powershell
python -m pip install -r backend\requirements.txt
Set-Location backend
alembic upgrade head
python -m uvicorn main:app --reload
```

If your terminal is already in `backend`, do not run `Set-Location backend` again; install with `python -m pip install -r requirements.txt`, then run the migration and server commands.

The API is at `http://localhost:8000`; OpenAPI docs are at `/docs`. On startup the app upgrades PostgreSQL to Alembic head and non-destructively copies legacy project media from `backend\database\storage\projects` to `backend\storage\projects`.

### Frontend

```powershell
Set-Location frontend
npm install
npm run dev
```

Open `http://localhost:3000`. To use another API origin, set `NEXT_PUBLIC_API_URL`.

## Migrate Existing Phase 1 Data

Back up the active SQLite file at `backend\storage\studio.db` and the media directory first. For an installation that never completed the prior migration, use `backend\database\storage\studio.db` only if the active file does not exist. Create an empty PostgreSQL database and set `DATABASE_URL`, apply migrations (`alembic upgrade head` from `backend`), copy media (automatic on app startup or manually), then from the repository root run:

```powershell
python scripts\migrate_sqlite_to_postgres.py --sqlite backend\storage\studio.db
```

For an installation that never completed the prior migration and has no active database at `backend\storage\studio.db`, use `python scripts\migrate_sqlite_to_postgres.py --sqlite backend\database\storage\studio.db` instead.

The importer preserves shared IDs, uses defaults for new Phase 2 fields, rewrites known local asset roots, refuses non-empty target tables, and does not delete SQLite rows or media. Verify row counts and media links before switching traffic. See the [database migration plan](./docs/04_database_design.md).

## Verify

```powershell
python -m pytest tests
Set-Location frontend
npm run typecheck
npm run build
```

Automated tests use a deterministic fake provider and do not call paid APIs. A PostgreSQL/OpenAI smoke test requires developer-owned credentials and explicit spending approval.

## Architecture

- `backend/api`, `backend/schemas`, `backend/services`, `backend/repositories`, `backend/models`, and `backend/migrations`: typed API, service, persistence, and schema-migration layers.
- `backend/services/ai/providers`: provider interface and OpenAI implementation. OpenAI SDK calls must remain inside provider classes.
- `backend/storage/projects`: local generated assets.
- `frontend/app`: Next.js route pages; `frontend/services/api.ts` contains typed API calls.
- `tests`: backend API and workflow tests with provider fakes.
- `scripts/migrate_sqlite_to_postgres.py`: non-destructive Phase 1 row importer.

Read [the Phase 2 implementation plan](./docs/09_phase_2_implementation_plan.md) and all specifications under `docs/` before extending scope.
