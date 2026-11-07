# API Contracts — Phases 2 and 3

Base URL: `/api/v1`

Local generation/selection APIs and `/film-plan` are specified in the
[local animation extension](./13_local_animation_extension.md#api).
InputBundle now adds `documents` (same supplied-file shape); scene/character
responses add `beat_number`/`facial_features`. Audio transcription returns
validated `transcript_words` and is required for multi-scene timestamp alignment,
including paired scripts. This supersedes equal-time splitting below.

All payloads are JSON. API-key values are never accepted or returned by these routes; configure `OPENAI_API_KEY` on the backend. Provider errors return a visible `502` (provider failure) or `503` (configuration unavailable). Budget overruns return `422`.

## Health

`GET /health`

```json
{"status":"ok"}
```

## AI Settings

`GET /settings/ai` returns the persisted singleton configuration and a boolean key indicator:

```json
{
  "provider":"openai",
  "model":"gpt-5",
  "image_model":"gpt-image-1",
  "default_budget":5.0,
  "default_wait_minutes":20,
  "api_key_configured":false
}
```

`PUT /settings/ai` accepts `provider`, `model`, `image_model`, `default_budget`, and `default_wait_minutes`; returns the same shape. Only the OpenAI provider is implemented in Phase 2. Saving never starts generation.

## Projects

- `POST /projects` — create a project without provider calls. Request: `prompt`, optional integer `target_seconds` (1-600, default 60), `max_budget`, `max_wait_minutes`. Legacy `target_minutes` still accepts matching fractional minutes; conflicting duration fields return `422`. Missing budget/wait use saved AI defaults. Response `201`: `{"project_id":1,"status":"created"}`. Project summaries/details expose both duration units.
- `GET /projects` — project summaries.
- `GET /projects/{projectId}` — project summary, prompt, budget/wait limits, `estimated_spend`, and any legacy Phase 1 `video_url`.
- `GET /projects/{projectId}/generation-estimates` — return `planning`, `story`, `characters`, `scenes`, `character_portrait`, `scene_image`, and `all_images` estimates. Each has `operation`, `estimated_cost`, `estimated_minutes`, `estimated_model_usage`, `estimated_api_calls`, and an estimate disclaimer.
- `DELETE /projects/{projectId}` with `{approved:true}` deletes the project, all dependent metadata and its media. Returns `200: {"status":"deleted"}`.
- `DELETE /projects/{projectId}/video` with `{approved:true}` deletes all exported versions and render checkpoints, retaining story, inputs, images, narration/audio and local motion clips. Returns the same deletion status.
- `PUT /projects/{projectId}/prompt` with `{approved:true,expected_prompt,prompt,target_seconds,max_budget,max_wait_minutes}` confirms a full sequence restart. Clears all prior content, imports, reviews, automatic consent and media; preserves historical spending. Returns `{"status":"created"}`. Stale original prompt returns `409`.
- Deletion/restart is blocked during active generation/planning. Media is moved to private `pending-deletions` storage before metadata is changed, restored on transaction failure, and removed after commit. Filesystem failures are reported, never a success-shaped response.

### Automatic stage generation

- `GET /projects/{projectId}/automatic-generation?mode=local_animation|still_images` returns the bounded combined artwork/GPU estimate, approval status and counts. Before planning, the quote uses at most six characters and twelve scenes.
- `POST` the same path with `{approved:true,estimate_id,render_mode}` approves missing-only generation on stage entry. Consent is prompt/duration/provider/model/rate/capability-bound. It does not approve the resulting content, narration/speech, regeneration or final export.
- `GET /projects/{projectId}/generation/{characters|scenes|animations}` returns `{job,missing}`. `job` uses the existing job status shape plus `operation`.
- `POST` the same path with `{retry:false}` starts or attaches to its serialized batch. Reentry never duplicates active jobs or automatically retries a failure. `{retry:true}` explicitly retries missing assets only; completed files remain. Portrait/scene estimates are reserved before calls; GPU clips use the isolated local provider one at a time.
- Story approval precedes portraits, character approval precedes scenes, scene approval precedes motion. Existing state-bound review confirmation applies to these routes. The frontend primary path is Plan → Story → Characters → Scenes → Timeline → Render.
- The project wait limit applies to the total image batch and to each GPU clip, not the total sequential GPU batch. The initial quote shows the total GPU time. Opening a GET endpoint never generates content.

## Planning and Story

- `POST /projects/{projectId}/analyze` — after showing the `planning` estimate, explicitly invoke the three text stages (story, character bible, scene plan). Optional `?refresh=true` regenerates and replaces the planning data. `200`: `{"status":"completed"}`. Estimated spend is reserved against the project budget before provider calls.
- `GET /projects/{projectId}/story` — title, summary, genre, target audience, three-act structure, full character list, and scene list.
- `PUT /projects/{projectId}/story` — save edits to those fields and the character/scene fields. Does not call the provider. `200`: `{"updated":true,"revision":"<saved-story revision>"}`. Explicit approval must use this saved revision, not a later unseen version.
- `POST /projects/{projectId}/story/regenerate` — refresh the story, character, and scene bibles; show the planning estimate first.
- `GET /projects/{projectId}/estimates` — legacy Phase 1 Economy/Balanced/Premium comparison. Its costs are illustrative and are not an OpenAI quote.

Character response fields include `id`, `name`, `role`, `personality`, `appearance`, `motivations`, `relationships`, `portrait_prompt`, `description`, `image_path`, and `approved`.

Scene response fields include `id`, `scene_number`, `title`, `description`, `visual_description`, `image_prompt`, `estimated_duration` (seconds), `image_path`, `status`, and `approved`.

## Character Images

- `GET /projects/{projectId}/characters` — list persisted character bibles and portrait paths.
- `POST /characters/{characterId}/portrait` — generate/regenerate one portrait after displaying its `character_portrait` estimate. `200`: `{"status":"completed"}`. Reserves the estimate against the project budget and stores an asset path.
- `PUT /characters/{characterId}` — approve/unapprove a character; no provider call.

## Scene Images

- `GET /projects/{projectId}/scenes` — list persisted scene plans and image paths.
- `POST /scenes/{sceneId}/generate` — generate the scene image after displaying its `scene_image` estimate.
- `POST /scenes/{sceneId}/regenerate` — regenerate that image after displaying the same per-image estimate.
- Both image endpoints return `200: {"status":"completed"}` and record the local generated asset path.
- `PUT /scenes/{sceneId}` — approve/unapprove a scene; no provider call.

## Metrics

`GET /projects/{projectId}/metrics` returns legacy export estimate/time, local export `actual_cost`, `estimated_ai_spend`, `actual_provider_cost: null` (invoice totals are not available), `actual_time`, image count, and video length when applicable.

## Phase 1 Legacy Video APIs

The existing video/job endpoints (`POST /projects/{projectId}/video`, `GET /projects/{projectId}/active-job`, `GET /jobs/{jobId}`, `GET /projects/{projectId}/video`, `/video/download`) remain for Phase 1 compatibility. They are not expanded in Phase 2; animation, voice, music, and new final-video generation functionality are out of scope.

## Phase 3 Production

All paths below are relative to `/api/v1`. Opening GET endpoints never calls an AI provider.

### Narration and speech

- `GET /projects/{projectId}/narration` returns `items`, `narration_estimate`, `audio_estimate`. Each item: `scene_id`, `text`, `recommended_seconds`, `audio_url`, `audio_seconds`, `stale`.
- `POST /projects/{projectId}/narration`: `{"approved":true,"estimate_id":"<narration estimate hash>","regenerate":false}`. Generates narration from all approved scenes and returns the same shape. If narration exists, explicit `regenerate:true` is required. Regeneration replaces text/audio links only after all text calls succeed.
- `POST /projects/{projectId}/narration/audio`: `{"approved":true,"estimate_id":"<audio estimate hash>"}`. Generates only missing audio, stores WAV metadata and measured duration, returns refreshed narration/estimates. Each successful scene is checkpointed. Retry requires the refreshed estimate.

Both require all scene image files; unapproved scene review requires the explicit skip dialog/token described below. Budget/wait checks remain mandatory before provider execution. Failed attempted calls retain reservations. Provider errors use the existing `502`/`503` handling.

### Timeline

- `GET /projects/{projectId}/timeline`: `{project_id, revision, scenes, duration_seconds, ready}`. Each scene has `scene_id`, `order`, `title`, `image_url`, `narration`, `audio_url`, `audio_seconds`, `duration_seconds`, `ready`.
- `PUT /projects/{projectId}/timeline`: `{"revision":"<current revision>","scenes":[{"scene_id":1,"duration_seconds":12}, ...]}`. Array order defines scene order. Include every project scene exactly once. Durations are integer seconds, 1-3600, and cannot truncate audio plus its 0.25-second tail. Returns the updated timeline.

### Render estimates and approval

`GET /projects/{projectId}/render/estimate?mode=local_animation|still_images` returns
a mode-bound estimate (default `local_animation`):

```json
{
  "estimate_id": "<64-character revision-bound hash>",
  "estimated_cost": 0.0,
  "estimated_runtime_seconds": 50.0,
  "estimated_storage_mb": 132.0,
  "estimated_audio_seconds": 65.2,
  "estimated_video_seconds": 80.0,
  "estimated_api_calls": 0,
  "model_usage": "Local FFmpeg / H.264 / AAC / 1280x720 / 24 fps",
  "notes": "Planning estimates, not provider quotes..."
}
```

Narration/audio estimates use the same schema with their own costs/model/call counts. Render storage includes segments and temporary output; source assets are additional.

`POST /projects/{projectId}/render`:

```json
{"approved":true,"estimate_id":"<render estimate hash>","mode":"local_animation","resume_job_id":null}
```

Requires a ready timeline and explicit current estimate approval. Local mode requires a current approved generated clip for **every scene**; missing clips return `409`, never a still-image fallback. Explicit `still_images` mode never invokes the video model and uses camera effects. `202` returns `{job_id, project_id, status, progress, current_stage, error, completed_scenes, video_url}`. An optional failed job ID resumes existing checkpoints only for an unchanged timeline/source mode. Model generation occurs in the preceding approved animation batch, not during FFmpeg export.

`GET /projects/{projectId}/render/status` returns the latest job in the same shape, or JSON `null` if no render exists. Status is `queued`, `running`, `completed`, or `failed`. `progress` is a percentage with one decimal place, derived from FFmpeg encoded media time between persisted scene checkpoints. Scene encoding occupies 0–80%; combining/validation occupies 80–99%; 100% is reserved for validated, published output. The status also includes `elapsed_seconds` for the current execution attempt and `estimated_remaining_seconds` (approximate, `null` on failure, zero on completion). ETA starts from the approved estimate, then extrapolates measured progress; queued resumes account for retained work. Files/checkpoints survive page reloads, and progress does not reset while resumed checkpoints are validated. Errors include a visible failure reason. Startup interruptions become failed jobs eligible for explicit resume.

### Playback, download, and metrics

- `GET /projects/{projectId}/video` retains `url` and adds `download_url`, `duration_seconds`, `audio_seconds`, `size_bytes`, `generation_seconds`, `estimated_cost`, `estimated_ai_spend`, `actual_provider_cost:null`, `render_job_id`, `render_mode`, `animated_scene_count`, and `generated_motion_seconds`. Legacy exports may have null production metrics and are labeled honestly. The latest successful MP4 stays available when a replacement fails.
- `GET /projects/{projectId}/video/download` returns `video/mp4` with attachment filename `project-{projectId}.mp4`.
- `/video` also returns `chapters`: ordered `{scene_id, title, start_seconds, duration_seconds, generated_motion_seconds}` entries from the **published render snapshot**, not the edited current timeline. Legacy exports without snapshots return an empty list.
- `/video` returns `playback_audio_url` for production exports. `GET /video/audio?render_job_id=<published ID>` locally decodes the exported MP4 audio into cached 16 kHz mono PCM WAV, for embedded browsers without AAC decoding. It never regenerates narration or changes the MP4. A changed export ID returns `409`; missing output returns `404`; decoding failures return an explicit `500`. Cache lives within render checkpoints, is removed with video/project deletion, and maintains the 15 GiB disk reserve.
- `GET /projects/{projectId}/metrics` uses published Phase 3 timeline duration/render time when available, rather than the original project target duration.

Missing approval returns `422`; stale estimates/revisions, incomplete assets, changed resume input, or concurrent mutations return `409`; missing projects/videos return `404`; budget or wait-limit violations return `422`. Never treat unavailable provider invoices as zero spend.

## Phase 3 Quality Upgrade

### Reviews and readiness

- `GET /projects/{projectId}/quality`: `{score, dimensions, explanation, blockers, reviews, story_revision, stage, character_scores}`. Dimensions: character consistency coverage, narrative continuity coverage, scene context coverage, asset completeness, approval coverage (0-100). `character_scores` maps character IDs to local identity-field/reference coverage. No vision/semantic evaluation or paid calls occur.
- `POST /projects/{projectId}/story/approval`: `{"approved":true,"revision":"<64-character current/saved revision>"}`. Returns the quality report. Missing story/scenes or stale revision returns `409`. Edits/reordering invalidate story approval.
- Portraits require story review, scene artwork requires character review, narration/audio requires scene review; render also checks story/characters and requires every scene image approved. Missing review responds `409` with:

```json
{"detail":{"code":"review_required","stage":"story","confirmation_token":"<state-bound hash>","message":"You are about to proceed without approving all story content.","consequences":"Unreviewed content can cause inconsistency and wasted spending.","required_action":"Review and approve story, or explicitly choose Continue Anyway for this request."}}
```

Only after user confirmation, retry that operation with `X-Workflow-Override: <confirmation_token>`. Multiple individually acknowledged review tokens may be comma-separated. Stale tokens are rejected. The override does not approve any content or bypass incomplete media, stale estimates, budget/wait limits, or job locks. The frontend permits only one confirmation per stage for a request; Cancel does not retry.

Characters now include `clothing`, `age`, `distinctive_traits`, `negative_prompt`, `reference_image_paths`, `generation_context`. Scenes include `motion_plan`, `generation_context`. Approved portraits are copied to immutable reference assets.

### Connected narration and motion

- Narration uses one whole-project provider call, with structured narrative arc and ordered bridges, rather than one independent call per scene. Narration items add `transition_text` (already spoken once in `text`). Whole-story/identity/scene-order/content changes mark the entire arc/audio stale; duration/image approval changes alone do not.
- Supplied narration generation/restoration has zero text-provider cost/calls and preserves supplied words. `regenerate:true` is still required before replacing links. Supplied audio is reused; missing synthetic speech is estimated separately.
- Missing slices of supplied original audio are restored locally through `/narration/audio`, never synthesized. The estimate has zero cost/calls, a positive local runtime when restoration is needed, and `model_usage:"Supplied audio / local restoration / no synthetic voice"`. Existing valid slices are reused.
- Timeline scenes add typed `motion_plan`: `camera` (`slow_zoom`, `pan`, `parallax`), `focus_x/y` (0-1), `transition` (`cross_fade`, `fade_black`, `fade_color`, `motion_blur`), `color` (`black`, `white`), `pacing` (`reflective`, `balanced`, `urgent`), `animation_instructions`, `motion_prompt`, `character_movement_prompt`, `execution:"camera_effects_only"`.
- `PUT /projects/{projectId}/scenes/{sceneId}/motion`: `{"revision":"<current timeline revision>","plan":{...}}`, returns quality report. Invalid focus/enum returns `422`; stale timeline `409`. Motion changes require a new render estimate/snapshot, not paid narration.

### Adaptive supplied inputs

- `POST /inputs/classify`: `InputBundle`, returns `{kinds, workflow, preserved, limitations, needs_transcription}`. Deterministic/local; no provider call.
- `POST /projects/{projectId}/inputs`: same bundle, returns `{classification, manifest}`. Import only before existing planning/import; otherwise `409`. Invalid/oversized/base64/media input returns `422` and rolls back database changes.
- `GET /projects/{projectId}/inputs`: same state or `null`. Local original-audio filesystem path is not returned.
- `GET /projects/{projectId}/inputs/transcription-estimate`: standard `ProductionEstimate`; no provider call.
- `POST /projects/{projectId}/inputs/transcribe`: `{"approved":true,"estimate_id":"<current hash>"}`, returns updated input state/transcript. Refuses duplicate transcription, stale estimate, budget/wait overrun and concurrent operations. Attempted calls retain reserved estimates on failure.

`InputBundle` fields:

```json
{
  "title":"Supplied project",
  "text":"Full story or script",
  "text_kind":"auto",
  "scenes":[{"title":"Arrival","description":"Mira arrives at the city","duration_seconds":15}],
  "characters":[{"name":"Mira","role":"Explorer","personality":"Curious","appearance":"Silver coat","motivations":"Find the map","relationships":"Trusts the guide","portrait_prompt":"Mira in her silver coat"}],
  "images":[{"name":"frame.png","content_base64":"<raw base64>","description":"Mira at the city gate"}],
  "audio":null
}
```

Text types: `auto`, `text_story`, `scene_descriptions`, `narration_script`, `character_definitions`. Classification adds `audio_file`, `image_collection`, `mixed_inputs` as applicable. Fields are optional except title defaults; at least one modality is required. At most 12 scenes/characters/images, 6000 text characters, 20 MB per file and 40 MB combined uploads. Images need descriptions and, with supplied scenes, one image per scene. Audio supports WAV/MP3/M4A/FLAC/OGG, max 10 minutes. Stored file names are generated, never supplied paths.

`/generation-estimates` and `/analyze` account for missing planning assets only after import. A full supplied story is not regenerated. Supplied scenes/characters/images remain unchanged. A supplied script/audio without scenes becomes one source segment; multiple supplied scenes use disclosed equal-word/equal-time splits, not word alignment. Original audio is retained locally and normalized. A script explicitly paired with audio avoids a paid transcription call.
