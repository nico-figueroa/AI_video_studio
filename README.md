# AI Video Studio

AI-powered story planning and end-to-end narrated video production. Generate and review storyboards, narration, and synthetic speech; arrange scenes; approve transparent estimates; render and download a playable MP4.

## Phase 3 Production Workflow

The [local animation and narrative extension](./docs/13_local_animation_extension.md)
adds hierarchical beats/scenes, film/continuity plans, document imports, timestamp-
aligned source audio, and optional reviewed local SVD clips. **Powered by Stability AI.**
The installed model is for authorized non-commercial evaluation; text-directed
character gestures/walking are unsupported. The guide supersedes earlier
"animation deferred" and equal-time input-splitting descriptions below.

The frontend opens at `/docs`, the studio's product/workflow/requirements/cost guide. The quality upgrade adds approved reference memory, whole-project narration with bridges, adaptive supplied inputs, explicit skip-review dialogs, local readiness scoring, and tone-aware camera/transition plans. Scores measure local coverage, not visual identity or semantic correctness.

To supply existing content, choose **Start from supplied assets** when creating a project, classify/correct the input type, and confirm import. Full stories, scenes, character definitions, captions/images, scripts, and original audio are preserved. Uploaded audio transcription requires a separate estimate approval. Missing assets only are generated. See the [quality upgrade implementation and verification plan](./docs/12_phase_3_quality_upgrade.md).

1. Complete draft planning, explicitly approve the story, generate/review character portraits, then generate/review scene images. Review skips require an explicit confirmation.
   On Plan, one bounded automatic-stage approval enables all missing portraits on
   Characters, all missing scene images on Scenes, and all missing local clips on
   Render. Initial artwork no longer needs individual Generate clicks. The main
   path advances through Story and Characters before Scenes.
2. Open **Timeline**, approve the narration estimate, and generate a single connected story with scene bridges (or restore supplied narration locally).
3. Review the separate speech estimate and approve generation of local WAV files.
4. Preview audio, reorder scenes, set durations, and save.
5. Open **Render** and approve estimated cost, runtime, storage, audio duration, and video length.
6. Track persisted stages/progress. Resume failed/interrupted renders with unchanged inputs.
7. Open **Your video** to play and download the H.264/AAC MP4 and review metrics.

Targets are selectable in seconds. Edit the original prompt and confirm a full
restart from Plan to clear the old sequence (including supplied inputs) while
retaining spending. Delete a whole project from Dashboard, or only its exported
videos/checkpoints from Your video. Active operations block deletion/restart.
Local-animation export requires a reviewed clip for **every** scene; the separate
still-image source mode never calls the video model. Existing exports do not
change automatically. The player reports the actual saved export source.

FFmpeg applies planned zoom/pan or simulated parallax and crossfade/black/white/blur transitions, preserves scene narration, and exports 720p / 24 fps MP4. Audio duration can extend a scene beyond its planned length. Rendering is local with no provider fee (electricity/hardware excluded); narration/speech are paid provider operations using your key. Actual invoice totals are unknown. All new AI calls use the existing provider abstraction.

See [the Phase 3 plan](./docs/10_phase_3_implementation_plan.md) and [user workflow](./docs/11_user_workflow.md). Optional generated local motion is now supported; lip sync, voice cloning, music, cloud GPU orchestration and RunPod remain excluded.

## Phase 2 Scope

- PostgreSQL persistence with SQLAlchemy and Alembic.
- OpenAI text and image generation behind the `AIProvider` interface.
- AI configuration at `/settings/ai`.
- Story Bible, Character Bible, Scene Plan, portrait, and scene image routes.
- Local project-scoped image storage with paths in PostgreSQL.
- Estimate-first UX, budget reservations, progress indicators, and explicit error reporting.

The Phase 2 planning workflow remains supported. The original silent Phase 1 export API remains for compatibility; the UI now uses the approved narrated Phase 3 workflow, and `/generate` redirects to render approval.

## Configure

1. Copy `.env.example` to `.env`.
2. Set `DATABASE_URL` to a PostgreSQL database using the `postgresql+psycopg://` driver.
3. Set `OPENAI_API_KEY` on the backend. The key is never saved in PostgreSQL or sent to the frontend.
4. Review the planning estimate rates against current OpenAI pricing. The estimates are not provider quotes; actual invoice totals are not reported by this app.
5. Review `OPENAI_SPEECH_MODEL`, `OPENAI_SPEECH_VOICE`, and `ESTIMATED_SPEECH_USD_PER_1K_CHARACTERS`. Speech uses a standard synthetic voice; no voice cloning. For uploaded audio, review `OPENAI_TRANSCRIPTION_MODEL` and `ESTIMATED_TRANSCRIPTION_USD_PER_MINUTE`.

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
Run only one backend process against a database at a time. Startup marks queued/running exports/renders and unfinished planning/narration/audio operations as interrupted, so starting a second process can invalidate work still running in the first. Completed render segments and speech files remain available for explicit retry/resume. Do not expect a distributed queue or automatic paid-operation retry.

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
npm test
npm run build
```

Automated tests use a deterministic fake provider and do not call paid APIs. A PostgreSQL/OpenAI smoke test requires developer-owned credentials and explicit spending approval.

The production tests encode/decode real MP4 video and audio. To additionally verify migration from Phase 2 and end-to-end persistence on your configured PostgreSQL database without touching its application tables:

```powershell
$env:STUDIO_TEST_POSTGRES="1"
python -m pytest tests\test_production_postgres.py
Remove-Item Env:\STUDIO_TEST_POSTGRES
```

This creates/removes a unique test schema and requires schema-creation privileges. Tests use synthetic audio fixtures, not paid OpenAI calls. Generated media and checkpoints remain locally owned; keep database/media backups together. The application does not automatically delete old audio or render checkpoints.

## Architecture

- `backend/api`, `backend/schemas`, `backend/services`, `backend/repositories`, `backend/models`, and `backend/migrations`: typed API, service, persistence, and schema-migration layers.
- `backend/services/ai/providers`: provider interface and OpenAI implementation. OpenAI SDK calls must remain inside provider classes.
- `backend/storage/projects`: local generated assets.
- `frontend/app`: Next.js route pages; `frontend/services/api.ts` contains typed API calls.
- `tests`: backend API and workflow tests with provider fakes.
- `scripts/migrate_sqlite_to_postgres.py`: non-destructive Phase 1 row importer.

Read [the Phase 2 implementation plan](./docs/09_phase_2_implementation_plan.md) and all specifications under `docs/` before extending scope.
