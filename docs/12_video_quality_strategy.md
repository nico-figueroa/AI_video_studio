# Video quality strategy

## Product standard

Optimize for a video a viewer wants to watch: one understandable story, stable
character identity and visual style, intentional movement/transitions, natural
narration and pacing. Hyperrealism is not a requirement. A technically valid MP4
or a high still-image score is not evidence of professional video quality.

## Generation strategy

1. Preserve and analyze the complete supplied story/script/document; classify
   what the user already supplied and generate only missing material.
2. Build one versioned story/character/visual bible and ordered beat/shot plan.
   Record characters, wardrobe, location, props, time, stakes, prior/current/
   next events, shot duration, motion and transition intent.
3. Generate continuity-conditioned video shots with stable references and
   explicit handoffs. Prefer a model's supported video continuation/editing
   path over unrelated image-to-video calls. Do not claim a model obeys actions
   or identity until representative clips prove it.
4. Compose one narration arc, with each bridge spoken once; preserve supplied
   scripts/audio and align speech to the actual edit.
5. Assemble a review candidate with audio sync and purposeful transitions.
   Keep source clips and an edit-decision manifest so weak shots can be
   replaced without regenerating the entire story.
6. Review candidate and address identified defects before final export.

The current scene/continuity and narration services are useful planning
foundations. The per-scene still-image-first workflow and experimental SVD clip
generation are not the target final-quality path.

## Quality assessment

Keep technical readiness separate from perceived quality. A weighted numeric
score must be calibrated against reviewed videos and must expose its evidence,
confidence, missing coverage and version. Do not let an unvalidated multimodal
model decide export readiness by itself.

Suggested initial rubric, to be calibrated with creator reviews:

| Dimension | Weight | Evidence |
|---|---:|---|
| Narrative completeness and continuity | 20% | Human review against source beats; missing/repeated events; scene order and references. |
| Character identity and visual-style consistency | 20% | Human side-by-side review of approved references and sampled shots; automated face/appearance signals only as supporting evidence. |
| Animation and action quality | 15% | Requested action occurrence, temporal stability, subject motion, camera motion, flicker/artifacts; reviewed sample clips. |
| Transition quality | 10% | Boundary continuity, abrupt cuts, black/frozen frames, audio overlap and transition intent. |
| Narration flow and audio | 15% | Arc/bridge coverage, speech completeness, clipping, silence, loudness and sync; human listen-through. |
| Pacing and shot variety | 10% | Beat durations, shot repetition, pauses and match to story tone. |
| Asset and technical integrity | 10% | Every shot/character/reference resolves; playable codecs, frame rate, dimensions, duration and complete audio. |

For each dimension, collect a 1–5 reviewer score plus automated evidence where
valid. Convert only after calibration to a 0–100 summary; keep dimension-level
scores visible. An overall score is advisory, never a substitute for review.
Technical blockers (corrupt media, missing required story beats, absent audio,
stale approvals) remain hard gates regardless of average score.

## Measurable checks

- Decode the entire output; verify expected dimensions/frame rate, duration,
  video/audio stream presence, monotonic timestamps and complete audio.
- Detect black/frozen/duplicate frames, severe luminance/flicker jumps, silence,
  clipping, unintentional gaps and transition boundary defects. Calibrate
  thresholds per content type and keep false-positive review.
- Compare shot order and durations with approved beats and narration; report
  missing, duplicated, stale or unmatched assets.
- Sample representative beginning/middle/end frames and high-motion boundaries
  for required human review; reviewers can reject only the affected shots and
  reassemble from approved replacements.
- Record model, version, prompt/context hashes, seed/settings, reference assets,
  per-shot output, retry attempts and the decision/review record.

Character embeddings, vision-language judging, optical-flow and audiovisual
models may assist triage, but scores can be biased or wrong. Validate precision
and recall on this product's stories and art styles before surfacing them as
quality evidence. Do not call a local field/reference coverage percentage a
visual identity score.

## Acceptance benchmark

Maintain a fixed, permission-cleared test set covering long-form source,
multiple characters, changing wardrobe/location, dialogue/narration, walking,
gestures, interaction, camera/environment motion, quiet scenes and transitions.
Blind-review candidate outputs at matched duration/resolution. Track reviewer
rubrics, defect rates, edit/retry count, model failure rate, p50/p90 latency,
actual infrastructure cost and retention size. Establish the release threshold
before switching defaults; repeat after any model, version, prompt template or
generation-parameter change.

## Workflow and user transparency

Show expected length, model/version, quality preset, uncertainty, runtime range,
cost ceiling and review stages before generation. Require explicit approval for
paid work and for final export. Show progress from persisted job events, not
simulated timers. Present a review candidate before final publication, retain
the prior successful video during replacement, and clearly distinguish
estimated cloud costs from actual Azure billing.

See [architecture](./09_azure_native_architecture.md) and
[animation approach](./15_animation_architecture.md).
