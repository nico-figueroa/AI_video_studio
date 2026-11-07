# Azure resource setup guide

This is a manual, reviewable provisioning runbook. It does not create resources
or imply that this repository is already deployed on Azure. Confirm region,
model access, GPU quota, organizational policy, network design, and cost with
the subscription owner before creating paid resources.

**Model lifecycle check, 2026-11-07:** do not deploy the documented Sora 2
versions `2025-10-06` or `2025-12-08`; Microsoft's retirement schedule lists
2026-07-15 and 2026-10-15 respectively. The continued presence of a video
overview page does not establish availability. Check for a newer supported
offer, or use a licensed open-weight video model on Azure ML GPU compute.
Apply the same lifecycle check to text, image, speech and transcription models.

## Naming, region and cost baseline

Use a short organization/project/environment/region convention such as
`rg-aivs-dev-westus2`, `staivsdevwestus2<unique>`, `kv-aivs-dev-westus2`,
`mlw-aivs-dev-westus2`, and `foundry-aivs-dev-westus2`. Storage accounts and
Key Vault names must be globally unique and follow Azure character rules. Add
environment, owner, cost-center, data-classification and expiry tags to every
supported resource.

Choose one region only after verifying all required Foundry models, GPU VM
families/quota, PostgreSQL, Storage, Key Vault and networking features are
available there. Prefer co-location to reduce latency, egress and cross-region
data movement. Select a second region only for an explicit recovery requirement;
do not copy sensitive source media across regions by default.

| Resource | Purpose | Estimated cost impact | Region guidance |
|---|---|---|---|
| Resource group | Lifecycle, policy and cost boundary | No direct charge | Same chosen deployment region for contained resources. |
| Microsoft Foundry account/project and deployments | Model catalog, hosted inference and evaluation | Usage varies by model, modality, resolution, duration and deployment mode; potentially the largest variable spend | Verify exact model deployment and quota in-region before creating. |
| Azure ML workspace/registry | Model, code, job and deployment lifecycle | Workspace metadata is small; registry storage, builds and compute are billable | Co-locate with Blob and GPU compute where supported. |
| Storage account / Blob containers | Inputs, references, job checkpoints, candidates and MP4s | Capacity, redundancy, transactions, retrieval tier and network egress | Keep with compute; choose redundancy from recovery objectives, not cheapest GB alone. |
| Key Vault | Secrets and keys | Usually low relative to inference; operations and premium HSM features add cost | Co-locate for policy and private connectivity. |
| GPU compute | Open-model inference and optional tuning | Highest variable infrastructure cost; GPU allocation/startup/idle time matters | Choose a supported GPU SKU by model VRAM and measured throughput; check quota and capacity. |
| Network/private endpoints | Private access, DNS, egress control | Private endpoints, NAT, gateways and transferred data can be material | Keep private data paths regional; budget egress and duplicated endpoints. |
| Monitoring/log analytics | Traces, metrics and audit | Ingestion, retention and query volume can grow with video jobs | Set retention and sampling before production traffic. |
| PostgreSQL Flexible Server | API state, job ledger and project metadata | DB tier, storage, backup and high-availability configuration | Same region/VNet; size from measured project/job concurrency. |
| Service Bus and Durable Functions | Durable queued work and orchestration | Queue operations, function executions and retained state | Co-locate with API and workers; establish retry/dead-letter policies. |
| Container Apps | Frontend/API and CPU job-control services | CPU/memory baseline and request scaling | Same region/VNet; do not host GPU inference in the API container. |

Use the [Azure pricing calculator](https://azure.microsoft.com/en-us/pricing/calculator/)
with your currency, agreement, region and SKU. A budget sends alerts; it is not
a hard spending cap that stops a running model or GPU.

## 1. Create a resource group

Sign in and select the intended subscription:

```powershell
az login
az account set --subscription "<subscription-id>"
az group create --name "rg-aivs-dev-westus2" --location "westus2" --tags environment=dev owner="<team>"
```

**Validate:** `az group show --name "rg-aivs-dev-westus2"` returns the expected
subscription, region and tags. Record the resource-group ID for scoped access
assignments.

## 2. Create Microsoft Foundry account and project

In the [Microsoft Foundry portal](https://ai.azure.com/), create or select a
Foundry resource in the chosen resource group, then create a project for this
studio and environment. The current Microsoft name is **Microsoft Foundry**
(formerly Azure AI Foundry). Follow the portal's current resource flow; resource
types, project dependencies and role names evolve.

In the project, inspect the model catalog and deploy only the candidate models
needed for the benchmark. Confirm the model/version, supported region, modality,
quota, pricing, responsible-AI restrictions, data handling, accepted reference
inputs and lifecycle/retirement notice. Treat a preview model as a pilot only.

**Validate:** the project's endpoint/deployment health is ready; an authorized
test identity can make a budgeted test call; the exact deployment appears in
the Azure portal and can be monitored. Do not put an endpoint key in frontend
configuration.

## 3. Create Azure Machine Learning workspace and GPU compute

Create an Azure Machine Learning workspace in the same region and resource
group, attaching the approved Storage, Key Vault, Application Insights and
container registry resources according to the organization's network policy.
If the portal creates dependencies automatically, review their names, public
access and cost settings before accepting.

Create a **GPU compute cluster**, not an always-on GPU VM, for queued
experimentation. Start with minimum nodes `0`, maximum nodes `1`, idle scale
down enabled, and an approved compute timeout. Select a GPU SKU only after
checking model peak VRAM, disk requirements, quota and region capacity. Higher
VRAM/H100-class hardware may be needed for large video models; a larger GPU
does not guarantee a better result. Keep the CPU/API cluster separate.

**Estimated impact:** GPU hours and attached OS/data disk dominate inference
cost. The cluster can still incur charges during startup, job execution, idle
grace periods, failed jobs, or retained disks.

**Validate:** workspace status is healthy; the cluster is `Succeeded`, can
scale from zero, obtains a node under the configured quota, downloads a
version-pinned test model, and scales back down after the idle period. Verify
the actual billable resources in Cost Analysis.

## 4. Create Storage and private containers

Create a StorageV2 account with secure transfer required, TLS 1.2 or higher,
public blob access disabled, and redundancy chosen from the recovery plan
(LRS/ZRS versus GRS/GZRS affects availability and cost). Use private containers
for `inputs`, `references`, `jobs`, `candidates`, and `published`. Define
lifecycle rules only after legal retention and recovery requirements are known.

Example CLI setup:

```powershell
az storage account create --name "<globally-unique-name>" --resource-group "rg-aivs-dev-westus2" --location "westus2" --sku Standard_ZRS --kind StorageV2 --https-only true --min-tls-version TLS1_2 --allow-blob-public-access false
az storage container create --account-name "<globally-unique-name>" --name "inputs" --auth-mode login
```

Create the remaining containers similarly. **Validate:** anonymous reads fail,
authorized managed identity can write/read only the assigned containers, and
upload/download checksums match. Account for capacity, write/list/read
transactions, snapshots/versions, geo-replication and egress in estimates.

## 5. Create Key Vault

Create a vault with Azure RBAC authorization, soft delete and purge protection
enabled, then assign secret access to the application identity only where
needed. Avoid vault-wide contributor permissions for runtime identities.

```powershell
az keyvault create --name "<globally-unique-name>" --resource-group "rg-aivs-dev-westus2" --location "westus2" --enable-rbac-authorization true --enable-purge-protection true
```

Prefer Microsoft Entra/managed identity authentication for Foundry, Storage,
PostgreSQL and Azure ML when supported; secrets should be the exception. Record
secret rotation ownership and dates.

**Validate:** an authorized administrator can add a non-production test secret;
the application identity can read only the required secret; an unrelated
identity is denied. Never print secret values in deployment logs.

## 6. PostgreSQL, durable jobs and application hosting

Create Azure Database for PostgreSQL Flexible Server in the selected region
with private networking, TLS, backups and a maintenance window. Choose compute,
storage, backup retention and high availability from measured recovery and
concurrency requirements. Migrate the existing Alembic schema and data using a
staged copy/verification runbook; do not point the running local app at a
partially migrated database.

Create a Service Bus namespace and a generation queue. Persist the job and
approval snapshot before enqueueing, and use an outbox/idempotency mechanism
for database-to-queue consistency. Configure delivery count, lock duration,
dead-letter inspection and retention; a dead-letter is an explicit failure,
not an automatic paid retry.

Create a Durable Functions app for long-running orchestration and a Container
Apps environment for the frontend/API and CPU-only job control. Use separate
managed identities and private connections. GPU inference remains an Azure ML
job or qualified hosted model call, never a request thread or general-purpose
API replica. Current application code does not yet implement these Azure
deployments; the provider/job migration must precede production traffic.

**Estimated impact:** PostgreSQL and app hosting are recurring baseline costs;
Service Bus and Durable Functions vary with job/event volume. Set database
backup and function/history retention intentionally.

**Validate:** the API can connect to PostgreSQL without a public database
endpoint, enqueue one idempotent job, and observe its durable completion and
failure path after a worker/orchestrator restart. Verify a duplicate message
does not launch duplicate paid generation.

## 7. Networking and access control

For production, place the application, PostgreSQL, AML compute and private
endpoints on the approved VNet design. Use private endpoints and private DNS
for Storage and Key Vault; disable public access where supported and tested.
Restrict egress to required Azure control-plane/model endpoints. Use HTTPS,
managed identities and least-privilege RBAC. Keep a documented break-glass
administrator path and test it separately.

Assign roles at the narrowest scope. Typical examples to validate with the
organization's current role catalog:

- Application managed identity: `Storage Blob Data Contributor` on only the
  required containers/account; `Key Vault Secrets User` only if a secret is
  required; database access through the approved identity/authentication mode.
- GPU job identity: read input/reference containers, write its job/candidate
  prefix, and access only the model artifact and monitoring resources it needs.
- Deployment operator: Foundry/AML deployment roles scoped to the project or
  workspace; separate from application runtime.
- Human reviewers: project-level read/review access, not key or compute admin.

**Validate:** test allowed and denied reads/writes from each identity, confirm
public endpoints are disabled or explicitly justified, and verify private DNS
resolves to private addresses from app and compute subnets.

## 8. Monitoring and cost controls

Connect API, orchestrator, AML jobs and model endpoints to Azure Monitor and
Application Insights. Log a correlation/job ID, project ID (not story text),
deployment/model version, input hash, estimate and approval revision, stage
times, retry count, GPU allocation time, output metadata and failure code.
Exclude secrets, full prompts, audio and raw uploads unless an approved
retention/consent policy requires them.

Create a Cost Management budget at subscription/resource-group scope with
early, threshold and forecast alerts. Add alerts for GPU cluster uptime,
endpoint replicas, failed/retried jobs, queue age, storage growth, egress,
quota exhaustion and error rates. Apply tags and a per-project estimate/
reservation gate in the application; Azure budgets do not stop consumption.
Define an operator runbook to disable deployments/compute if spend is abnormal.

**Validate:** generate one test job and follow its correlation ID through API,
queue, model/AML, Blob and PostgreSQL; verify alerts and dashboards show
resource consumption. Confirm an estimate includes actual deployment billing
units and a visible uncertainty range.

## Completion checklist

- [ ] Foundry model and region are reachable under the real subscription.
- [ ] AML workspace, GPU quota and scale-to-zero behavior are verified.
- [ ] Storage is private, checksummed and permission-tested.
- [ ] Key Vault and managed-identity access are least-privileged.
- [ ] Network isolation/DNS and required egress are tested.
- [ ] Monitoring, budget alerts, retention and incident procedures exist.
- [ ] Resource names, IDs, regions, model version, rates and quota are recorded.
- [ ] A test generation was explicitly approved and its billable usage reconciled.

## Official references

- [Create a Microsoft Foundry project](https://learn.microsoft.com/en-us/azure/foundry/how-to/create-projects)
- [Microsoft Foundry model retirement schedule](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-retirement-schedule)
- [Azure Key Vault overview](https://learn.microsoft.com/en-us/azure/key-vault/general/overview)
- [Azure Blob redundancy](https://learn.microsoft.com/en-us/azure/storage/common/storage-redundancy)
- [Azure Machine Learning online endpoints](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-deploy-online-endpoints?view=azureml-api-2)
- [Azure GPU VM sizes](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes-gpu)
- [Azure Machine Learning pricing](https://azure.microsoft.com/en-us/pricing/details/machine-learning/)
- [Azure Blob Storage pricing](https://azure.microsoft.com/en-us/pricing/details/storage/blobs/)
- [Azure pricing calculator](https://azure.microsoft.com/en-us/pricing/calculator/)
