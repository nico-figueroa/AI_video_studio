# Local model cleanup plan

This is a staged review plan, not authorization to delete model files. The
current local SVD deployment is still referenced by production services and is
the default render mode for projects unless explicitly changed. Do not remove
its weights, Python environment, dependencies or code until the Azure cutover
gates below pass.

## Cleanup gates

1. Approve an Azure-hosted model and commercial/use terms for the intended
   product; verify access in the target subscription and deployment region.
2. Pass the fixed quality benchmark for characters, requested actions,
   continuity, output technical integrity, cost and runtime.
3. Implement Azure provider adapters, asynchronous durable jobs, Blob asset
   paths, estimates/approval, monitoring, failure recovery and private access.
4. Migrate project defaults and user settings without changing saved render
   snapshots. Keep prior MP4s playable and retain outputs required for audit.
5. Run a small opt-in pilot; verify retry, restore, spend reconciliation,
   privacy controls and rollback.
6. Announce the deprecation window and provide a user-approved export/backup
   path. Only then make a separately reviewed removal change.

## Removal scope after approval

- Remove default/local-SVD dispatch from stage generation and animation service.
- Remove the local worker launcher, SVD provider, isolated worker manifest,
  license-acceptance setting, local model path setting and legacy UI copy.
- Remove the SVD-only worker requirements and onboarding/download steps.
- Add a migration for defaults/job semantics only if needed; do not rewrite
  deployed migrations or delete historical animation/video metadata.
- Update tests, environment documentation, architecture guides and model
  cleanup reporting. Keep project media and published videos unless users
  explicitly request their deletion.
- Delete only the specifically inventoried `workers\local_animation\model` and
  `workers\local_animation\.venv` directories after verifying their resolved
  paths and obtaining explicit approval. Do not clear global caches or unrelated
  Python environments as part of this cleanup.

The measured workspace inventory is in
[MODEL_CLEANUP_REPORT.md](./MODEL_CLEANUP_REPORT.md). No files were removed.
