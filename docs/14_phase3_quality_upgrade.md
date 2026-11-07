# Phase 3 quality upgrade plan

## Baseline

The repository already implements much of the original quality-upgrade scope:
long-form story/beat planning, continuity context and approved character
references, one connected narration arc with bridges, adaptive document/audio
inputs, review safeguards, nonrepeating loading messages, local readiness
coverage, camera/transition effects, and local experimental SVD animation.
See [12_phase_3_quality_upgrade.md](./12_phase_3_quality_upgrade.md) and
[13_local_animation_extension.md](./13_local_animation_extension.md) for the
as-built contracts and limitations.

The strategic gap is output quality and deployment: visual generation still
uses the external OpenAI provider and optional two-second local SVD, while jobs
and media remain local and in-process. Azure does not become an automatic quality
improvement merely by changing hosting.

## Upgrade sequence

### A. Characterize and baseline

- Assemble a permission-cleared benchmark set and blinded human rubric.
- Measure current storyboard, image, SVD, transition, narration and final
  assembly quality, runtime and cost; retain outputs as a comparison baseline.
- Label current `QualityAssessmentService` results accurately: readiness and
  metadata coverage, not semantic/visual coherence.
- Inventory input gaps: current parser supports TXT, MD, DOCX, extractable PDF,
  JSON, YAML and CSV; RTF and supplied MP4/MOV ingestion are not implemented.

### B. Azure provider and infrastructure

- Add a versioned provider contract for asynchronous video generation,
  reference-conditioned image/video, model capability discovery, status,
  cancellation and result retrieval.
- Keep Foundry and Azure ML deployment credentials server-side; prefer Entra
  managed identity. Do not expose model endpoints or storage keys to the browser.
- Move durable project assets to private Blob Storage, relational state to Azure
  Database for PostgreSQL, and job dispatch to Service Bus plus durable workers.
- Add estimate/approval and idempotent checkpoint semantics before routing any
  paid production request to Azure.

### C. Quality-first generation path

- Keep supplied story/script content and generate only missing inputs.
- Replace unrelated scene-image generation as the required path with a
  beat/shot plan and reference-conditioned video generation when the selected
  model supports it.
- Retain portraits/keyframes as optional reference assets and keep the existing
  whole-story narration arc, but align shots and audio to the actual generated
  timeline.
- Preserve the composer for audio sync, transitions, technical validation and
  final export. Do not use basic pans/fades as a substitute for generated
  character/environment motion.
- Maintain per-shot review/replacement and the last successful export.

### D. Quality gates and input completeness

- Upgrade assessment to combine technical media checks, narrative coverage,
  asset/revision integrity, model evidence and human ratings with clear
  confidence. Keep hard technical blockers separate from advisory scores.
- Provide a candidate review step before publication; allow corrections without
  re-generating accepted work.
- Add RTF and MP4/MOV ingestion only with bounded parsers, explicit ownership,
  malware/content controls, size/duration limits, provenance, estimates and
  missing-only analysis. Video input should inform story/asset preservation;
  never silently treat an uploaded video as a generated result.

### E. Deprecate local SVD safely

- Keep local SVD available only while it is a useful, clearly labeled
  experimental option and while existing projects depend on it.
- Remove it only after the Azure model passes quality, licensing, privacy,
  cost, runtime and recovery gates. Follow the
  [cleanup plan](./13_model_cleanup_plan.md); never auto-delete weights.

## Required pre-production transparency

Before a request show what will be generated, what supplied content is reused,
model/version and capabilities, duration/output settings, estimated cloud/GPU,
storage and network costs, runtime range, quality tier, approval stages and
known limitations. Bind confirmation to that snapshot. Surface failures and
retain estimated-spend reservations when billing is uncertain.

## Definition of done

- Azure deployment is not claimed complete until a real subscription-backed
  integration test passes without exposing user data or secrets.
- Benchmark outputs meet predeclared human quality thresholds and all technical
  checks; cost/runtime bounds are measured and disclosed.
- Restart/retry uses persisted jobs and verified checkpoints; no duplicate paid
  work occurs automatically.
- User inputs are preserved, missing assets alone are generated, and approved
  content is never silently replaced.
- Previous videos and local assets survive deployment rollback.
- Local model removal remains a separate, explicitly approved task.

See [Azure architecture](./09_azure_native_architecture.md),
[setup](./10_azure_setup_guide.md), [quality strategy](./12_video_quality_strategy.md),
and [model cleanup report](./MODEL_CLEANUP_REPORT.md).
