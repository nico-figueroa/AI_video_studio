# System Architecture

## Phase 3 production extension

The [local animation extension](./13_local_animation_extension.md) supersedes
the deferred-only contract below: `AnimationService -> AnimationProvider ->
LocalSVDProvider -> isolated Python 3.12/CUDA subprocess -> reviewed local MP4`.
PostgreSQL jobs serialize GPU use globally; selected clips join immutable render
snapshots and are composed with original narration. No external animation API is
used. Narrative decomposition, scene bridges/film plans, document imports and
word-timestamp source-audio alignment are described in that guide.

Approved stage automation uses `StageGenerationService -> checkpointed Job ->
ImageAssetService / AnimationService -> existing provider abstractions`. Initial
artwork/motion starts on the appropriate stage entry under bounded prior consent;
regeneration, content review, narration and final export remain separate.
Render source mode is estimate/snapshot-bound: local mode requires reviewed
clips for every scene; still-image mode is explicit. `ProjectLifecycleService`
provides locked, confirmed deletion/restart with reversible private media staging.
Second-based targets are stored as fractional minutes for legacy compatibility.
Legacy media copying is one-time, so deleted files cannot reappear on restart.

### Quality upgrade

`/` redirects to the frontend `/docs` guide. All project routes share readiness/review coverage, current stage, and missing-content actions. `LoadingMessageService` uses locale-keyed, randomly shuffled nonrepeating catalogues (20 unique messages each for story, character, scene, narration/audio, and rendering).

`WorkflowService` enforces story review before portraits, character review before scene artwork, and scene review before narration/audio. Initial Phase 2 planning creates draft bibles; it does not approve any of them. A structured `409 review_required` describes the skipped stage, consequences, action and state-bound confirmation token. The frontend shows Cancel/Continue Anyway. Explicit override applies only to reviews, never missing production media, stale estimates, budget/wait limits or active-job locks. Successful overrides are audited. Final render also checks story/character review and requires approved scene images.

`CharacterMemoryService` reconstructs identity/clothing/age/traits/prompts from persisted characters, retains immutable approved portrait copies, and conditions every image request on bibles and up to six available reference files. `StoryMemoryService` supplies story, acts, characters, ordered scene history, prior/current/upcoming events, locations/visuals and approved earlier image links. `QualityAssessmentService` computes local context/reference coverage, asset availability and approval coverage; it is not visual identity or semantic verification.

`InputAnalysisService` deterministically classifies supplied modalities with user-correctable text types. Imports preserve full stories, character definitions, scene plans, described images, narration and original audio. Only missing planning assets are generated. Bounded base64 uploads are decoded locally and stored under generated names; audio is normalized with FFmpeg. `AIProvider.transcribe_audio` executes only after separate cost/runtime approval and reservation. Supplied scripts/audio are retained rather than rewritten; multi-scene imports use explicitly disclosed equal-word/equal-time splits, not alignment.

`NarrationComposerService` invokes `AIProvider.compose_narration` once with the complete project context. Structured opening/development/resolution and ordered scene text/bridges are validated before replacing any narration. Spoken bridges are prepended exactly once. Story/identity/scene-order/content changes invalidate the whole generated arc and its audio; image approval and audio-driven duration changes do not.

`SceneMotionPlanner` persists tone-driven camera/focus/pacing/transition and deferred character-animation instructions. `VideoComposerService` executes only local camera effects: slow zoom, pan, simulated two-plane parallax, crossfade, black/white fade and horizontal blur. Half-second outgoing visual handles allow transitions without shortening or overlapping narration; audio is concatenated at the original scene boundaries. Final output is decoded before atomic publication.

`AnimationProvider` declares `generate_motion_plan`, `animate_character`, and `animate_scene` as future contracts. No implementation executes animation or connects OpenAI video, Runway, LTX Video, Wan, Mochi, cloud GPUs or RunPod.

The Phase 2 planning layers below remain in use. Production adds:

```text
Timeline / Render / Video Next.js pages
  -> typed production API routes
  -> NarrationService -> NarrationComposerService -> AIProvider.compose_narration / generate_speech
  -> TimelineService -> persisted scene order/duration and linked assets
  -> RenderService -> persisted job/snapshot/checkpoints
      -> VideoComposerService -> local FFmpeg segments -> validated MP4
  -> PostgreSQL (narrations, render_jobs, videos) + local project media
```

Every new provider operation has an estimate-bound approval and reserves estimated spending. Speech uses a standard synthetic voice; all OpenAI SDK calls remain inside `OpenAIProvider`. Audio is WAV with measured duration; MP4 is H.264/AAC, 720p, 24 fps, with image zoom/pan and fades through black. No generated motion, animation, lip sync, voice cloning, music, cloud GPU orchestration, or RunPod.

Rendering uses in-process background tasks and one backend process per database. PostgreSQL project locks and a partial unique index serialize render claims; active renders block story/image/timeline/approval mutations and legacy exports. Startup marks interrupted jobs failed but retains checkpoints; explicitly approved Resume validates completed segments and requires an unchanged timeline revision. Only a fully validated file replaces the project's published video.

See [Phase 3 plan](./10_phase_3_implementation_plan.md) and [user workflow](./11_user_workflow.md). Historical Phase 2 exclusions below describe that phase only and do not prohibit this extension.

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
- Phase 3: `generate_narration(title, description, seconds)`
- Phase 3: `generate_speech(text, output_path)`

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