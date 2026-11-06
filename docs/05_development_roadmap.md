# Development Roadmap

## Phase 0 — Scaffold (complete)

FastAPI and Next.js setup, project structure, and local media storage.

## Phase 1 — Workflow MVP (complete; under review)

Project workflow prototype, SQLite storage, placeholder planning/images, estimates, and local slideshow export. Phase 2 preserves the existing export but does not extend it.

## Phase 2 — AI Planning Studio (current)

### Workstreams

1. **PostgreSQL and migrations:** SQLAlchemy 2.x schema, Alembic upgrade path, SQLite row/media migration runbook, PostgreSQL integration checks.
2. **Provider architecture:** `AIProvider` interface, OpenAI text/image implementation, server-side key handling, provider selection/model settings.
3. **Story Bible:** structured title, summary, genre, audience, three-act structure, and character seeds.
4. **Character Bible:** role, personality, appearance, motivations, relationships, and portrait prompt.
5. **Scene plan:** numbered scenes with title, description, visual description, image prompt, and estimated duration.
6. **Images:** generated portraits and scene images in local project storage; PostgreSQL asset paths.
7. **Estimation and UX:** per-stage cost, duration, model-usage, and API-call estimates; pre-call budget reservation; loading, progress, and explicit error states.
8. **Verification:** provider-mocked service/API tests, migration tests, frontend typecheck/build, and manual OpenAI/PostgreSQL smoke test using developer-owned credentials.

### Exit Criteria

- Fresh database reaches head using Alembic; no runtime `create_all`.
- Existing SQLite data can be imported without destroying the backup.
- All provider-backed operations use the abstraction and structured validation.
- The UI displays estimates before the user starts every provider operation.
- Settings, bibles, scene plans, and asset paths persist and can be retrieved.
- The test suite and frontend checks pass.

## Phase 3 — Production Media (not part of this implementation)

Possible future work: animation, voice, music, and final-video generation. Do not start Phase 3 functionality in Phase 2.