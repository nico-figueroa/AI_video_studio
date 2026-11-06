# GitHub Copilot Agent Master Prompt — Phase 2

Before implementation, read every file under `/docs` and inspect the existing Phase 1 implementation. Follow the scope and contracts in this documentation.

## Mission

Build an AI-powered planning and story-generation studio that makes cost, time, model usage, and API calls visible before provider requests and preserves user review/editing between stages.

## In Scope

- Replace SQLite runtime persistence with PostgreSQL, SQLAlchemy 2.x, and Alembic migrations; document and support importing existing SQLite data.
- Implement `backend/services/ai/providers/base.py` and `openai_provider.py` with the `AIProvider` operations for story, character bible, scene plan, character portrait, and scene image.
- Keep every OpenAI SDK call inside provider classes. Services and routes use the abstraction.
- Use structured/validated JSON for story, character, and scene planning.
- Persist projects, Story Bibles, Character Bibles, Scene Plans, AI configuration, generation estimates/spend reservations, and generated asset paths.
- Generate portraits and scene images into local project storage.
- Add `/settings/ai` and Phase 2 planning/story/character/scene frontend behavior.
- Show estimates for cost, duration, model usage, and API calls before every generation request; show progress and errors explicitly.

## Technology

- Frontend: Next.js App Router, TypeScript, Tailwind CSS.
- Backend: FastAPI, Pydantic 2, SQLAlchemy 2.x, Alembic.
- Database: PostgreSQL via `DATABASE_URL`; SQLite only for tests or importing the Phase 1 database.
- Provider: OpenAI text and image APIs, server-side key in `OPENAI_API_KEY`.
- Assets: local `backend/storage/projects/{project_id}` paths, recorded in PostgreSQL.

## Exclusions

Do not implement animation, voice, music, Redis/Celery, or new final-video generation. The existing Phase 1 slideshow export may remain unchanged.

## Architecture Constraints

- Routes validate and delegate; services own behavior; repositories own database access.
- Do not use `metadata.create_all` in application startup; migrate with Alembic.
- Do not persist or return the OpenAI API key.
- No request may invoke a provider before its estimate is shown and the user explicitly starts generation.
- Reserve estimates against project budget before provider calls; report that estimates are not provider quotes.
- Handle provider failures without returning success-shaped output.
- Keep frontend API contracts typed and include loading/progress/error states.

## Verification

Run backend tests, migration checks, frontend `npm run typecheck`, and `npm run build`. Add mocked provider tests; do not make real paid API calls in automated tests. Manually verify PostgreSQL/OpenAI only with developer-owned credentials and approved spending.
