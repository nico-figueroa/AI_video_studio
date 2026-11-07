# Azure-native architecture

**Status:** target design; no Azure resources or Azure provider are provisioned
or connected by this document. Research checked 2026-11-07. Model availability,
preview status, quota, regional support, licensing, and pricing must be
re-verified in the target subscription before deployment.

## Decision

Optimize for coherent, watchable output rather than preserving the current
generation pipeline. First benchmark a managed video-generation model that is
actually deployable in the subscription. If it meets the quality bar, use it for
shots and retain Azure-hosted open-weight inference as a qualified alternative.
Do not assume Sora 2 is a production dependency. Although its overview remains
online, Microsoft's retirement schedule lists versions `2025-10-06` and
`2025-12-08` with retirement dates of 2026-07-15 and 2026-10-15 respectively,
both before this audit date. Do not provision those versions. A newer offer
must be verified in the subscription and its current lifecycle checked.

When a managed model is unavailable or fails the benchmark, deploy a selected,
licensed open-weight model on Azure GPU compute. Choose its serving mode from
real workload measurements: queued batch jobs with scale-to-zero for long,
asynchronous generations; managed online inference only when interactive
latency justifies paying for provisioned replicas. Avoid a permanently running
GPU as the default.

## Target request and asset flow

```text
Next.js
  -> FastAPI on Azure Container Apps (CPU, managed identity)
      -> Azure Database for PostgreSQL Flexible Server
      -> private Azure Blob Storage (inputs, references, candidates, exports)
      -> Microsoft Foundry text/image/video deployments
      -> Azure Service Bus job queue
          -> durable workflow/orchestrator
              -> Foundry hosted video operation OR Azure ML GPU batch job
              -> technical media checks and candidate assembly
  -> review candidate, approve export, publish MP4 to Blob Storage
```

The API persists a job and immutable input/model/estimate snapshot before
enqueuing it. Workers claim idempotent jobs, write checkpoints and outputs to
private Blob Storage, then update PostgreSQL. Polling reads persisted job state;
it never starts generation. Use an outbox or equivalent transactional enqueue
pattern so a database commit cannot strand a job. Keep GPU execution outside
the API and orchestration process.

Use Microsoft Entra ID and managed identities between application services.
Use Key Vault only for credentials that cannot use managed identity, model
provider keys, and signing material. Keep source uploads, references, and
unpublished video private; serve approved playback using short-lived scoped
URLs or an authenticated media endpoint. Keep a project-scoped manifest with
content hashes, model/version, prompts, reference IDs, timings, estimate and
approval revision.

## Current architecture decisions

| Component | Decision | Quality-first rationale and target |
|---|---|---|
| Story Bible and narrative analysis | **KEEP, simplify** | Preserve the complete source, acts, story beats, characters, timeline and user edits. Treat the bible as shared context, not as multiple competing prompt summaries. |
| Character Bible and approved references | **KEEP** | Identity, wardrobe, age, distinctive traits and approved references are valuable conditioning inputs. Keep versioned, immutable references; disclose that references improve rather than guarantee identity. |
| Scene generator | **REPLACE its image-first role** | Generate a coherent beat/shot plan with previous/current/next context, continuity handoffs and timing. Avoid treating every scene as an unrelated prompt. |
| Image generator | **REPLACE as the default final visual path; KEEP optionally** | Use image generation for user-requested stills, reference portraits, or carefully approved keyframes. Do not require a separate still for every shot when the selected video model accepts story and reference context directly. |
| Narration generator | **KEEP, improve** | Keep the existing whole-project arc and spoken bridges. Reuse supplied scripts/audio and align narration timing to the edit; never ask scene-local calls to independently summarize a story. |
| Video composer / FFmpeg | **KEEP, refocus** | Retain assembly, audio sync, codec normalization, transitions, chapters, technical validation and export. It is an editor/QC layer, not a way to disguise disconnected stills as animation. |
| `QualityAssessmentService` | **KEEP, expand** | Existing scores are local coverage/readiness checks, not semantic or visual judgments. Add measurable media checks and reviewed visual/narrative ratings; clearly label sources and confidence. |
| OpenAI API provider | **REPLACE in Azure deployment** | Keep a provider interface, but add Azure-native adapters using Entra authentication where supported. Do not send production workloads to an external OpenAI endpoint. |
| Local SVD provider and GPU worker | **REMOVE only after cutover gate** | Its two-second image-to-video clips do not meet the movement or continuity target. Preserve until new provider parity, rollback, and project-asset handling are verified. |
| In-process FastAPI background tasks | **REPLACE** | They are not durable across restarts or horizontally scaled API replicas. Use a queue, persisted job state, idempotent workers and resumable checkpoints. |
| Local project media | **REPLACE for Azure deployment** | Store source files, references, checkpoints and exports in private Blob containers; keep PostgreSQL metadata and content hashes. |
| PostgreSQL/Alembic model | **KEEP, migrate** | Retain relational workflow/revision semantics. Host PostgreSQL on Azure Database for PostgreSQL Flexible Server and migrate schema/data without rewriting deployed revisions. |
| Estimate and approval gates | **KEEP, expand** | Reserve estimates before spend, bind approvals to model/rate/input versions, show uncertainty and retain attempted-call reservations. |

## Azure service comparison

| Option | Best fit | Quality/control | Cost/operations | Decision |
|---|---|---|---|---|
| Microsoft Foundry managed models | Text, image, and video when the exact model is offered to the subscription/region | Lowest serving burden; capabilities, reference conditioning, duration and lifecycle are model-specific | Usually usage-based for hosted inference; separate storage, orchestration and output costs | First candidate for the quality bake-off, never assume availability from a public model page alone. |
| Foundry-managed compute, when offered for the selected model | Managed deployment of a supported custom/open model | More model choice/control than a fixed hosted API; check quotas, supported deployment format and region | Compute-backed charges while capacity is provisioned; confirm scale-to-zero and idle billing for that deployment type | Evaluate for bounded experiments; not a universal substitute for Azure ML. |
| Azure Machine Learning GPU batch/managed compute | Asynchronous open-weight video generation and custom inference | Pin exact weights, code, sampler, resolution, precision and runtime; permits model-specific conditioning | GPU VM/cluster time, startup/idle time, disk, registry, Blob, logs and network; autoscale cluster to zero when safe | Recommended open-weight path for queued jobs after a quality/license test. |
| Azure Machine Learning managed online endpoint | Low-latency, frequent inference | Stable endpoint contract; full model/serving control | Provisioned replicas can incur charges while idle; autoscaling does not make every GPU endpoint free at zero load | Use only if measured interactive demand and latency justify its baseline cost. |
| User's local SVD worker | Local prototype and historical assets | Current implementation produces short 512x288 clips with no text-directed character actions | Local GPU, 4.20 GB weights plus 5.54 GB isolated environment in this workspace | Not the Azure target; keep until cutover is verified. |

Public video-generation overview pages can outlive a model version. They do
not prove that a model is deployable in a specific tenant, subscription,
region, quota, or production agreement. Validate the in-portal catalog and
model retirement schedule immediately before any decision or estimate.

## Quality and migration gates

1. Build a fixed test set of representative long-form stories, supplied scripts,
   named characters, reference images, action types, and transition cases.
2. Compare candidate models at the same duration, aspect ratio and review
   criteria. Preserve prompts, settings, seeds where supported, generated
   outputs and evaluator notes.
3. Require explicit human review for identity, motion, scene continuity, pacing
   and narration. Machine scores alone cannot promote a model.
4. Verify regional access, capacity/quota, content policy, commercial rights,
   reference inputs, async job lifecycle, output retention and actual billing.
5. Add the provider adapter, estimate model, asynchronous job state, Blob paths,
   monitoring and rollback before switching project defaults.
6. Run a small, explicitly approved Azure pilot. Keep local code/data intact
   until recovery, cost reconciliation and quality thresholds pass.

## Research sources

- [Microsoft Foundry video generation overview](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/video-generation)
- [Microsoft Foundry model retirement schedule](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-retirement-schedule)
- [Create a Microsoft Foundry project](https://learn.microsoft.com/en-us/azure/foundry/how-to/create-projects)
- [Azure ML online endpoints](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-deploy-online-endpoints?view=azureml-api-2)
- [Azure GPU VM sizes](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes-gpu)
- [Azure pricing calculator](https://azure.microsoft.com/en-us/pricing/calculator/)

For resource creation, see [10_azure_setup_guide.md](./10_azure_setup_guide.md).
