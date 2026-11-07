# Azure-hosted animation architecture

## Recommendation

Prefer a qualified, managed text/image/video generation model when it produces
the best reviewed motion and character continuity for this product. If no
available managed deployment passes the benchmark, host a licensed open-weight
video model on Azure GPU compute and run it as an asynchronous, queued job.
Choose Azure Machine Learning batch/scale-to-zero compute for long generation
jobs; use a managed online endpoint only when measured interactive demand and
latency justify its provisioned GPU cost. Foundry-managed compute is an option
only where the exact model/deployment mode is currently supported and its
availability, scaling and billing are verified.

Microsoft's video-generation overview still describes Sora 2 as a preview,
but the model retirement schedule lists versions `2025-10-06` and
`2025-12-08` with retirement dates of 2026-07-15 and 2026-10-15 respectively.
As of 2026-11-07, do not deploy those versions. Verify any newer offer in the
subscription and its lifecycle before testing; otherwise use the open-weight
GPU path. Do not assume an overview page means deployment access.

## Approaches

| Approach | Character/action potential | Consistency/control | Main trade-off |
|---|---|---|---|
| Managed video-generation API | Direct prompt/image/video-conditioned motion; quality and action support depend on current model | Provider-managed model; input references and continuation tools vary; test identity drift and clip duration | Lowest GPU operations; model availability, per-output billing, limits and lifecycle are external dependencies. |
| Open-weight video model on Foundry-managed compute | Can support text/image/video-to-video depending on model; possible custom inference pipeline | Version-pinned weights, code and conditioning; greater control over sampling and identity adapters | Check that the exact model/runtime is supported; GPU cost, regional quota and deployment limitations remain. |
| Open-weight model on Azure ML GPU batch/compute | Enables long-running character, environment and camera-motion inference | Full control of model build, reference inputs, schedulers, checkpoints and packaging | Highest engineering/operations effort; manage GPU utilization, startup, autoscale, model licensing and reproducibility. |
| Local Stable Video Diffusion in this repository | Short image-to-video clips; no text-directed action controls in the current adapter | Local seed/parameters and source image; no Azure scale or production guarantees | Current 14-frame / 512x288 / 7fps output is experimental, non-commercial and does not meet the stated character-animation target. |

Open model candidates must be selected from the current Foundry/AML catalog or
approved model registry and qualified by exact weights/revision. Names such as
Wan, LTX-Video or HunyuanVideo are evaluation leads, not a promise of Azure
availability, commercial rights, support, or equal capability. Review each
model's weights license, code license, acceptable-use policy, training-data
terms, redistribution rules and output restrictions before a pilot.

## Motion and continuity design

- **Character identity:** store immutable, approved multi-view/reference assets
  and structured age, face, wardrobe, traits and negative constraints. Pass only
  supported references; record hashes and which references each shot used.
- **Action:** describe one primary subject action and its start, middle and end
  state per shot (for example, approaches, pauses, then opens the door), with
  secondary motion separately. Validate walking, gestures, head motion, blinking
  and interaction as test cases; prompt text is not proof the action happened.
- **Idle/environment:** specify subtle breathing/weight shift, wind, weather,
  background movement and exclusions to avoid competing motion.
- **Camera:** plan a stable lens/framing and a single intentional camera move
  (pan, tracking, dolly, push-in) per shot. Check model support and handheld
  jitter; do not promise camera controls from prose alone.
- **Shot-to-shot continuity:** preserve the same character/style/location
  context; pass the prior shot's approved endpoint/reference or model-supported
  continuation input; plan overlapping handles and motivated transitions.
  Inspect boundary frames and regenerate/replace only failing shots.
- **Narration/audio:** treat synthesized/model audio as optional unless
  explicitly selected and separately estimated. Preserve the approved narration
  arc, dialogue and sync; never silently replace user audio.
- **Assembly:** normalize frame rate, dimensions, color and audio, then compose
  transitions and validate the complete video. Interpolation/upscaling can
  introduce artifacts and cannot create semantically correct action.

## Deployment and runtime contract

Persist `queued/running/completed/failed/cancelled` state, model/version,
capability snapshot, immutable shot inputs, estimate/approval, attempt count,
timestamps, measured GPU time, output object IDs, checksums and quality-review
results. A queue consumer claims a job idempotently; workers write to a
job-scoped Blob prefix and only publish after all outputs pass validation.
Store resume checkpoints when the selected model allows safe resumption.
Never automatically retry a potentially billed generation.

Scale GPU capacity to zero between asynchronous jobs where the chosen service
supports it. Keep concurrency and per-project job limits explicit; reserve
quota/capacity before accepting a duration promise. Record model load, cold
start, sampling, decode, upload and queue time separately. User-facing ETA
should be based on measured p50/p90 per model/SKU/preset, not an assumed
constant number of seconds per final-video second.

## Capability bake-off

Run the same stories, approved character references and motion requests through
each eligible candidate. Include close and wide shots, multiple recurring
characters, wardrobe changes, walking, gestures, head movement, blinking,
interaction, idle motion, camera movement, environment movement and transitions.
Review full clips and shot boundaries; rate character identity, action fidelity,
temporal smoothness, style consistency, story relevance, artifacts, output
quality, latency and actual cost. Include failure and retry rate.

Promote only a model/version/preset that passes the predeclared quality bar,
commercial/privacy/security review and cost/runtime envelope. Keep a second
provider path or a controlled rollback until the model has production history.

See [Azure architecture](./09_azure_native_architecture.md),
[GPU cost model](./11_gpu_cost_model.md), and
[video quality strategy](./12_video_quality_strategy.md).
Check the [current model retirement schedule](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-retirement-schedule)
before selecting a managed model version.
