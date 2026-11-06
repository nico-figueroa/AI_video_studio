# System Architecture

## Phase 2 Request Flow

```text
Next.js App Router
  -> typed API client
  -> FastAPI routes (/api/v1)
  -> project / story / AI configuration services
      -> SQLAlchemy repositories and PostgreSQL
      -> AI estimation service
      -> AIProvider interface
          -> OpenAIProvider (only layer importing/calling the OpenAI SDK)
  -> local project storage (image files; paths in PostgreSQL)
```

Routes validate requests and return typed responses. Services own business rules and orchestration. Repositories own persistence. Frontend components never access the database or provider SDKs.

## Frontend

- Next.js App Router, TypeScript, and Tailwind CSS.
- `/settings/ai` manages provider/model defaults and project defaults.
- Project routes support estimate-first planning, story review, character review, and scene review.
- Every generation control displays estimated cost, duration, model usage, and calls; loading/progress and provider errors remain visible.

## Backend

- FastAPI and Pydantic 2 request/response models.
- SQLAlchemy 2.x and PostgreSQL through `DATABASE_URL`.
- Alembic migrations run on application startup and can also be run with `alembic upgrade head`.
- Services: AI configuration, generation estimation, story orchestration, project management, and local image storage.
- The legacy Phase 1 slideshow export remains present, but Phase 2 adds no animation, voice, music, or final-video behavior.

## Provider Architecture

`backend/services/ai/providers/base.py` defines `AIProvider`:

- `generate_story(prompt, target_minutes)`
- `generate_character_bible(story)`
- `generate_scene_plan(story, characters, target_minutes)`
- `generate_character_portrait(prompt, output_path)`
- `generate_scene_image(prompt, output_path)`

`OpenAIProvider` returns validated Pydantic data for text operations and writes generated image bytes to the supplied project-local path. OpenAI SDK calls are forbidden outside provider classes. Provider choice and model identifiers are persisted as non-secret configuration; `OPENAI_API_KEY` is read only from the backend environment and never returned or stored in PostgreSQL.

## Estimation and Budget Controls

The AI estimation service estimates each text stage and each individual image request, including model, token/image usage, cost, duration, and call count. Estimates use configured planning rates (`ESTIMATED_TEXT_USD_PER_1K_TOKENS`, `ESTIMATED_IMAGE_USD_PER_IMAGE`); they are explicitly not provider quotes or guaranteed invoice amounts. Before a call, the backend checks and reserves its estimate against the project budget. The provider invoice is not available from this application.

## Data and Media

- PostgreSQL stores projects, generated bibles, scene plans, estimates, AI configuration, jobs, and generated asset paths.
- Alembic owns schema creation and changes; application startup must not call `metadata.create_all`.
- Image assets remain local under `backend/storage/projects/{project_id}`. Static media paths are exposed; database and environment files are not.
- SQLite migration procedure and rollback safeguards are in [04_database_design.md](./04_database_design.md).

## Deferred

Distributed workers, cloud object storage, animation, voice/music production, and final video generation are later-phase work. Do not add them in Phase 2.