# Development Roadmap

## Phase 3 local animation extension

See [scope, deployment and verification](./13_local_animation_extension.md).
Hierarchical narrative plans, continuity bridges/film plans, document formats,
timestamp alignment and reviewed local SVD generation extend the baseline.
Instruction-driven character actions remain unsupported by SVD, not completed
Phase 4 features. This supersedes deferred-animation-only descriptions below.

## Phase 0 — Scaffold (complete)

FastAPI and Next.js setup, project structure, and local media storage.

## Phase 1 — Workflow MVP (complete; under review)

Project workflow prototype, SQLite storage, placeholder planning/images, estimates, and local slideshow export. Phase 2 preserves the existing export but does not extend it.

## Phase 2 — AI Planning Studio (complete)

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

## Phase 3 — End-to-End Production (implemented)

- Provider-based narration and standard synthetic speech with estimates and explicit approval.
- PostgreSQL narration/audio metadata, video records, render snapshots, and resumable scene checkpoints; Alembic `0002_phase3`.
- Scene timeline with ordering, duration validation, source invalidation, and revision protection.
- Local FFmpeg image zoom/pan, fade transitions, narration mixing, and H.264/AAC MP4 output.
- Timeline, render approval/progress/recovery, and video playback/download routes.
- Real FFmpeg encode/decode tests, deterministic provider tests, isolated PostgreSQL upgrade/production verification, frontend typecheck/build.

See the [implementation plan](./10_phase_3_implementation_plan.md) and [workflow](./11_user_workflow.md).

## Deferred beyond Phase 3

### Phase 3 quality upgrade (implemented; not Phase 4)

- Documentation-first landing, global readiness/review status, nonrepeating localized-message catalogues.
- Explicit review guards and auditable, state-bound Continue Anyway confirmations.
- Adaptive import/classification; preserved story/script/scenes/characters/images/audio; missing-only planning and separately approved provider transcription.
- Persistent character/reference and story/event context for all artwork; honest local coverage scoring.
- One connected narration arc with validated scene bridges and whole-story invalidation.
- Persisted tone-aware motion/focus/pacing, actual crossfade/black/white/blur exports and simulated parallax; narration duration preserved.
- AnimationProvider contract and deferred prompts only; no animation execution.
- Provider-fake service/API checks, malformed uploads, review/staleness tests, actual transition encode/decode, PostgreSQL migration/production tests, frontend build/typecheck and shuffle-cycle tests.

See the [quality upgrade plan](./12_phase_3_quality_upgrade.md). Paid-provider identity/coherence still needs human review; no numerical score guarantees it.

Animation, lip sync, voice cloning, generated motion, music generation, distributed workers, cloud GPU orchestration, and RunPod integration are not implemented.