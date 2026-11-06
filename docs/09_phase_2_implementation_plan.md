# Phase 2 Implementation Plan

## Goal and Boundary

Deliver a working AI planning studio on PostgreSQL: Story Bible, Character Bible, Scene Plan, character portraits, scene images, model settings, and estimate-first UX. Do not add animation, voice, music, or new final-video generation.

## Implementation Sequence

### 1. Data foundation

- Configure PostgreSQL through `DATABASE_URL`; add SQLAlchemy PostgreSQL driver.
- Define the project, character, scene, estimate, generated-asset, job, and AI-configuration schema.
- Create Alembic revision `0001_phase2`; apply migrations at startup and support `alembic upgrade head`.
- Add non-destructive SQLite row import and local media-copy procedures. Preserve the SQLite source until row counts and asset paths are verified.
- Validate the fresh migration on test SQLite and a developer-owned PostgreSQL instance.

### 2. Provider and configuration

- Define Pydantic response contracts for the three text outputs.
- Add `AIProvider` and `OpenAIProvider`; structured JSON is validated before use.
- Centralize provider/model construction in the AI configuration service.
- Persist provider, text model, image model, default budget, and default wait time. Read `OPENAI_API_KEY` from environment only.
- Confirm with a repository search that no OpenAI SDK calls exist outside provider implementations.

### 3. Planning orchestration

- Estimate three planning calls before execution and reserve the total against the project budget.
- Invoke story → character bible → scene plan via the provider abstraction.
- Validate non-empty character output and scene count (4-12); persist all fields in a single story update transaction.
- Keep original data intact if a provider or persistence step fails; expose provider error details.

### 4. Image generation

- Calculate a per-image estimate and reserve it before calling the configured image model.
- Generate one portrait or scene image per explicit action. Do not start bulk image generation automatically.
- Write the image under the project storage directory and persist the local path in the owning character/scene and generated-assets record.
- Preserve approval semantics: a new or regenerated image resets approval.

### 5. Frontend and transparency

- Implement `/settings/ai` and use saved defaults on project creation.
- Make project creation side-effect-free; show a planning estimate before the generate action.
- Render all story/character/scene fields and expose editing where specified.
- Show per-image estimate before each action, remaining budget, in-flight status, and provider error.
- Keep existing Phase 1 MP4 pages explicitly labeled legacy and out of Phase 2 scope.

### 6. Verification and release

- Unit/API tests use a deterministic fake `AIProvider`; no paid calls in test runs.
- Test settings persistence/key non-disclosure, estimate-before-generation responses, budget rejection, structured output persistence, asset paths, failures, and retry behavior.
- Run Alembic on a clean PostgreSQL DB; import a copy of the Phase 1 SQLite DB and verify row counts/representative media.
- Run backend tests, frontend typecheck, and production build. Document unmet PostgreSQL/OpenAI manual checks rather than simulating them.

## Data Migration Runbook

See the detailed [database design and migration plan](./04_database_design.md). The checked-in importer requires an empty migrated target and preserves IDs. Keep the SQLite database and media as a backup; the importer never deletes its source.

## Key Decisions

- OpenAI is the only implemented provider for this phase; the interface allows future providers without placing SDK logic in business services.
- Model and image price estimates are configurable planning rates, not live provider quotes. Actual provider invoices are not reported by the application.
- Provider keys are environment-only secrets, not editable/stored UI settings.
- Local filesystem storage remains in place; cloud storage and distributed workers are deferred.

## Definition of Done

- [ ] Fresh PostgreSQL schema upgrades to Alembic head.
- [ ] SQLite import procedure preserves row IDs, defaults new columns, rewrites known media paths, and retains backups.
- [ ] All required structured story/character/scene/image data persists and retrieves.
- [ ] Every AI action displays an estimate and checks remaining budget before provider invocation.
- [ ] Settings persist without exposing the API key.
- [ ] Backend tests, frontend typecheck, and frontend production build pass.
- [ ] No Phase 3 functionality is added.
