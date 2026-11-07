# AI Video Studio

Phase 3 extends this vision into narrated, image-based MP4 production. See the [production plan](./10_phase_3_implementation_plan.md) and [end-to-end workflow](./11_user_workflow.md). The Phase 2 scope below is historical.

## Mission

AI Video Studio is an ethical AI-powered planning and story-generation studio. It turns a creator's idea into editable story, character, and scene bibles, then generates reference portraits and scene images. Cost, time, model usage, and API-call estimates are shown before each provider request.

## Core Principles

- **Transparency first:** Show the estimated cost, duration, model usage, and API calls before generation.
- **Human in the loop:** Creators can review and edit generated story and planning data before generating images.
- **Budget protection:** Reserve each displayed estimate against the project's budget before sending provider requests.
- **No surprise consumption:** Explain that estimates are planning figures and cannot guarantee provider billing or latency.
- **Separation of concerns:** AI business logic calls a provider interface; only provider implementations call model SDKs.
- **Local asset ownership:** Generated image files remain in project-scoped local storage, with their paths recorded in PostgreSQL.

## Phase 2 Goal

Support PostgreSQL persistence and Alembic migrations; configurable OpenAI text and image models; Story Bible, Character Bible, and Scene Plan generation; character portraits and scene images; per-operation estimates; and a transparent AI settings experience.

Phase 2 does not add animation, voice, music, or final-video generation. The existing Phase 1 slideshow export is legacy functionality and is not extended by this phase.

## Target Audience

- YouTube creators
- Educational content creators
- Independent filmmakers
- Hobbyist storytellers
- Digital marketing creators