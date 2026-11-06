# Phase 2 Requirements

## Objective

Turn the Phase 1 workflow prototype into a working AI-powered planning and story-generation studio without adding later production stages.

## In Scope

1. Replace the active SQLite database with PostgreSQL, SQLAlchemy 2.x, and Alembic-managed schema migrations.
2. Provide an `AIProvider` interface for story, character-bible, scene-plan, portrait, and scene-image generation. Business logic uses the interface; OpenAI SDK calls stay in provider classes.
3. Use OpenAI for structured JSON story, character, and scene planning responses, and for image generation.
4. Persist the Story Bible (title, summary, genre, target audience, three-act structure), Character Bible (role, personality, appearance, motivations, relationships, portrait prompt), Scene Plan (number, title, description, visual description, image prompt, estimated duration), AI settings, and asset paths in PostgreSQL.
5. Save generated portraits and scene images under project-scoped local storage.
6. Show cost, duration, model usage, and API-call estimates before every operation. Reserve estimates against the project's budget before provider calls.
7. Provide `/settings/ai` to configure provider, text model, image model, default budget, and default wait time. The OpenAI key remains a backend environment secret.
8. Provide clear loading, progress, and provider-error states on the planning, story, character, and scene routes.

## Phase 2 Workflow

Create a project without starting generation → review the estimate → explicitly generate story, character, and scene bibles → review/edit the output → review per-image estimates → generate and review individual portraits and scene images.

## Out Of Scope

- Animation or final-video generation beyond the pre-existing Phase 1 export
- Voice or music generation
- Redis/Celery job processing
- Multi-user billing, community sharing, fine-tuned models, or mobile applications
- Additional provider implementations beyond OpenAI

## Acceptance Criteria

- A clean PostgreSQL database reaches the schema through Alembic migrations.
- Existing SQLite projects can be copied with `scripts/migrate_sqlite_to_postgres.py`; project media is copied separately and retained as a backup.
- No OpenAI SDK call exists outside `backend/services/ai/providers/`.
- Every Phase 2 generation request has a corresponding estimate endpoint and is budget-checked server-side.
- Story, character, scene, settings, and generated-asset records round-trip through PostgreSQL.
- The frontend requires an explicit action after showing estimates and reports failures without success-shaped fallbacks.