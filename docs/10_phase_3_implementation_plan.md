# Phase 3 Implementation Plan

The [Phase 3 quality upgrade](./12_phase_3_quality_upgrade.md) extends this baseline with connected narration, reference memory, adaptive inputs, review safeguards and planned motion/transitions. Its contracts supersede the original independent-scene narration and simple-fade behavior below.

## Baseline and boundary

`phase_3` was verified identical to `origin/main` at `ba2737b` (Phase 2 merge). Build on its PostgreSQL/Alembic persistence, provider interface, estimate reservations, approval semantics, and local media ownership.

Deliver narrated image-based MP4 production. Do not implement animation, lip sync, voice cloning, generated motion, music generation, cloud GPU orchestration, or RunPod.

## Implementation sequence

1. **Persistence:** Add revision `0002_phase3`, retaining all Phase 2 rows. Create `narrations`, `render_jobs`, and `videos`. Scene deletion cascades to its narration; render snapshots and published video metrics remain historical records.
2. **Provider extension:** Add `generate_narration(title, description, seconds)` and `generate_speech(text, output_path)` to `AIProvider`. OpenAI implements structured narration and standard-voice WAV speech. SDK calls remain inside provider implementations.
3. **Narration:** `NarrationService` generates text only from approved scenes, reserves the displayed estimate, stores source fingerprints and timing recommendations, and exposes stale narration after story edits. Regeneration requires a separate explicit confirmation.
4. **Speech:** Show a separate estimate before generating missing WAV audio. Persist file paths, measured duration, speech model, and voice. Reserve each attempted call before execution; checkpoint successful files so retries skip them. Failed attempted calls retain reservations because billing cannot be ruled out.
5. **Timeline:** `TimelineService` links scenes, images, text, and audio. Persist order and duration through existing scene fields. Update order transactionally in two passes to respect the unique scene-number constraint. Require an optimistic revision token and exact project scene membership. Never truncate narration.
6. **Composition:** `VideoComposerService` creates per-scene H.264/AAC segments with zoom/pan, fade-in/out transitions through black, padded narration, and 24 fps / 720p output. Combine segments into fast-start MP4 and decode both streams before publication.
7. **Rendering:** `RenderService` requires approval of a revision-bound estimate and a complete timeline. Claim one active job under the project lock and partial unique index. Persist stages, percentages, immutable timeline/estimate snapshots, and completed-scene checkpoints. Publish only validated output; keep the prior successful video on failure.
8. **Recovery:** Startup marks interrupted renders failed, keeping checkpoints. Explicit Resume reuses the same job only if the timeline revision still matches. Validate reusable segments; rebuild damaged/missing ones. Changed input requires a new job. Interrupted narration/audio can be retried explicitly.
9. **API and UI:** Add typed narration, audio, timeline, render estimate/start/status APIs; extend video metadata without breaking its existing URL field. Add timeline/render/video workflow pages, explicit estimate approval, reorder/duration editing, audio previews, progress/retry/resume, playback, download, and generation metrics. Redirect the legacy Generate page to render approval.
10. **Verification:** Run deterministic provider tests, real FFmpeg encode/decode and audio checks, migration/retention tests, concurrency and recovery tests, an isolated PostgreSQL integration test, frontend typecheck, and production build. Do not send paid API calls in tests.

## Estimates and approval

- Narration: configured text-token planning rate and one whole-project coherent-arc call; supplied scripts restore locally without text-provider calls.
- Speech: configured per-1,000-character planning rate and missing audio only.
- Local rendering: $0 provider fee, excluding electricity/hardware. Quality-upgrade runtime heuristic: `max(5, video_seconds * 1.6 + scene_count * 2)`, accounting for motion/transition composition.
- Render storage estimate includes output, retained scene segments, and temporary final export; roughly `video_seconds * 0.55 * 3 MB`. Existing source media is additional.
- Audio estimates are recommendations before synthesis. Once speech exists, actual WAV duration determines the minimum scene duration. Rendering estimates use that final timeline, not the original target length.
- Reject stale estimates, missing approval, incomplete media, exceeded budget/wait limits, or concurrent mutations. Estimates are not guaranteed provider quotes or latency promises.

## Verification commands

```powershell
python -m pytest tests
$env:STUDIO_TEST_POSTGRES="1"
python -m pytest tests\test_production_postgres.py
Remove-Item Env:\STUDIO_TEST_POSTGRES
Set-Location frontend
npm run typecheck
npm run build
```

The PostgreSQL test creates and removes only a uniquely named test schema using the configured database. It requires schema-creation privileges and does not migrate or modify the application's existing schema.

## Operational limits

One backend process per database; in-process background execution, not a distributed queue. A graceful restart does not automatically spend money or resume work. Segment completion, rather than individual frames, is the durable progress boundary. Render execution time accumulates across failed/resumed attempts; an abrupt process stop preserves time only through its last checkpoint. Media/checkpoints are retained locally; no automatic asset garbage collector or storage quota is introduced. Provider invoice totals remain unavailable.

## Acceptance

A project can advance from approved scene images to persisted narration, synthetic speech, an ordered timeline, approved render, observable progress, validated H.264/AAC MP4 playback, and an attachment download. A failed/interrupted render can resume its unchanged checkpoints without regenerating speech or losing the prior video.
