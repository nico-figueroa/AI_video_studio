# Azure GPU and generation cost model

**Status:** estimation method, not a quote. GPU rates, model availability,
billing units, regional offers and agreement discounts change. Refresh the
calculator inputs whenever a model, SKU, region, resolution or serving mode
changes.

## Cost components

For a hosted model, use its actual meter (for example generated video seconds,
resolution/quality tier or request units) plus storage, orchestration and
network costs. For self-hosted open weights:

```text
GPU cost =
  allocated GPU-node seconds / 3,600 × regional GPU-node hourly rate
  + startup / warm-up / billed idle grace time
  + any separately billed CPU, OS/data disk, registry or orchestration compute
```

Estimate the full project:

```text
project estimate =
  planning/text/image/speech provider meters
  + hosted video meter OR GPU inference cost
  + candidate/final storage and transactions
  + database, queue, app and monitoring allocation
  + expected network egress
  + retry/quality-review reserve
```

Keep fixed infrastructure cost separate from per-project variable cost; do not
divide a GPU subscription-wide monthly bill into a single video without
disclosing the allocation method.

## GPU runtime estimate

Do not derive runtime from seconds of final video alone. For each pinned
model/version, GPU SKU, precision, frame rate, resolution and shot type,
benchmark representative clips and measure p50/p90:

- cold startup, model load and warm-up;
- generation seconds per output video second;
- frames, diffusion steps and peak VRAM;
- decode, interpolation/upscale (if used), validation and failed attempts;
- concurrency and queue time;
- output size and upload duration.

Estimate GPU hours from observed runs by quality tier and scene count, then add
a documented uncertainty reserve. Use p90 for user-facing completion windows;
show the benchmark sample size and last-updated date. Re-estimate when model
version, SKU, frame count, resolution or reference conditioning changes.

## User-facing quality tiers

Treat Economy/Balanced/Premium as named, measured presets—not quality
guarantees. Each preset must identify the deployed model/version, resolution,
frame rate, clip length, reference strategy, generation attempts, finishing
operations and expected runtime range.

| Preset | Candidate policy | Cost/runtime behavior |
|---|---|---|
| Economy | Lowest benchmark-qualified hosted tier or smaller GPU/model preset that still passes technical and human minimums | Lower resolution/shorter clips or fewer variants; disclose likely limitations and keep review gates. |
| Balanced | Default benchmark-qualified model and measured production settings | Optimize the quality/latency/cost frontier; one primary attempt plus explicit user-approved retries. |
| Premium | Highest passing model/resolution/conditioning and larger GPU where benchmarks demonstrate an improvement | More GPU time/storage and potentially longer wait; extra variants or upscale only when their measured gain justifies cost. |

Never label an unqualified or unavailable model “Premium.” If a preset changes
deployment, rates or model settings, bind its estimate ID to that exact
configuration and invalidate old approvals.

## Estimate inputs and budget control

Before any paid call, estimate and disclose:

- model/vendor/deployment/version, region and billing unit;
- projected seconds/frames/resolution and number of shots/attempts;
- GPU SKU and allocated runtime range for self-hosted inference;
- startup/warm-up, queue and end-to-end runtime ranges separately;
- retained source, reference, intermediate and final GB-months;
- transaction counts, egress assumptions and fixed-cost allocation;
- uncertainty range, excluded charges, remaining project budget and retry policy.

Reserve the upper estimate (or show a clearly explained range plus the reserved
ceiling) before enqueueing. On failure retain the reservation if the provider
may have billed. Reconcile estimates against Azure Cost Management at resource
and deployment level; do not report unavailable invoice data as zero.

Set Azure budgets/alerts as a separate operational safeguard. They alert but
do not enforce a project-level hard cap. Application approvals, workload
limits, deployment shutdown procedures and GPU autoscaling are still required.

## Storage and network

Count source media, immutable character references, generated shots, failed
attempts retained for review, candidate renders, checkpoints and published
exports. Estimate Blob storage from peak retained GB × tier/redundancy rate ×
retention months. Add transactions, snapshots/versions, replication and
retrieval fees. Include outbound egress and cross-region copying; private
endpoints do not make data transfer free.

Apply lifecycle deletion only to explicitly disposable intermediates after
retention, legal hold and render-resume requirements are defined. Never delete
source material, approved references, or published versions as a cost shortcut.

## Estimate verification

1. Get current regional rates for the actual Foundry deployment or GPU VM,
   disks, Blob tier/redundancy, network and monitoring from Azure pricing.
2. Run a bounded approved benchmark with representative prompts and references.
3. Capture allocation/startup/idle time and output size from telemetry.
4. Compare predicted and actual resource consumption for multiple runs.
5. Publish the sample count, p50/p90 error and rate-refresh timestamp to users.
6. Invalidate estimates on changes to model, version, region, rate card, GPU,
   generation parameters or storage policy.

See [setup and cost controls](./10_azure_setup_guide.md) and
[Azure pricing calculator](https://azure.microsoft.com/en-us/pricing/calculator/).
