# API Contracts — Phase 2

Base URL: `/api/v1`

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

- `POST /projects` — create a project without provider calls. Request: `prompt`, optional `target_minutes`, `max_budget`, `max_wait_minutes`. Missing budget/wait use saved AI defaults. Response `201`: `{"project_id":1,"status":"created"}`.
- `GET /projects` — project summaries.
- `GET /projects/{projectId}` — project summary, prompt, budget/wait limits, `estimated_spend`, and any legacy Phase 1 `video_url`.
- `GET /projects/{projectId}/generation-estimates` — return `planning`, `story`, `characters`, `scenes`, `character_portrait`, `scene_image`, and `all_images` estimates. Each has `operation`, `estimated_cost`, `estimated_minutes`, `estimated_model_usage`, `estimated_api_calls`, and an estimate disclaimer.

## Planning and Story

- `POST /projects/{projectId}/analyze` — after showing the `planning` estimate, explicitly invoke the three text stages (story, character bible, scene plan). Optional `?refresh=true` regenerates and replaces the planning data. `200`: `{"status":"completed"}`. Estimated spend is reserved against the project budget before provider calls.
- `GET /projects/{projectId}/story` — title, summary, genre, target audience, three-act structure, full character list, and scene list.
- `PUT /projects/{projectId}/story` — save edits to those fields and the character/scene fields. Does not call the provider. `200`: `{"updated":true}`.
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
