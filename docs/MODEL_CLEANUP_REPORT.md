# Local model cleanup report

**Audit date:** 2026-11-07

**Scope:** repository-local worker/model folders, manifests, code/configuration
references and project-media size. No files were deleted. Global Hugging Face,
CUDA, pip or other user-level caches were not inventoried.

## Measured local footprint

| Path | Observed size | Contents / disposition |
|---|---:|---|
| `workers\local_animation\model` | 4.20 GiB, 23 files | Pinned Stable Video Diffusion FP16 model snapshot; includes `.safetensors` weights, configs and license/readme. **Model payload; retain pending cutover.** |
| `workers\local_animation\.venv` | 5.54 GiB, 27,186 files | Isolated Python 3.12 environment for CUDA/PyTorch inference. **Environment, not model weights; retain pending cutover.** |
| `backend\storage\projects` | 0.30 GiB | User/project assets, generated images, audio and video. **Not a model cache; preserve and back up with database.** |

Sizes are workspace measurements and can change. They do not include external
caches or resources configured through `LOCAL_ANIMATION_MODEL_DIR` and
`LOCAL_ANIMATION_PYTHON`.

## Model and dependency inventory

- Model ID: `stabilityai/stable-video-diffusion-img2vid`
- Pinned revision: `9cf024d5bfa8f56622af86c884f26a52f6676f2e`
- Worker: `workers\local_animation\worker.py`
- Provider: `backend\services\ai\providers\local_svd.py`
- Isolated manifest: `workers\local_animation\requirements.txt`
- Worker dependencies include CUDA PyTorch, Diffusers, Transformers, Accelerate,
  Safetensors, Hugging Face Hub, Pillow, imageio-ffmpeg, imageio, NumPy and
  Pydantic. The backend requirements do not install PyTorch/Diffusers.
- The worker is launched by `AnimationService`; stage estimates, automatic
  stage generation, render mode, quality/readiness, API routes and tests also
  reference local animation. Its local animation source is the current default
  render mode for new projects.
- `LOCAL_ANIMATION_LICENSE_ACCEPTED`, `LOCAL_ANIMATION_PYTHON` and
  `LOCAL_ANIMATION_MODEL_DIR` are documented runtime configuration. The
  deployment currently limits this model use to authorized non-commercial use.
- `.gitignore` excludes the local model directory and virtual environments; the
  measured binary weights/environment are not tracked source code.

## Usage and safety implications

The current adapter generates 14 frames at 512×288 and 7 fps (about two
seconds), with no text-directed action controls or guaranteed character
identity. Existing animations and project media may still be referenced by
database snapshots and published MP4s. Do not delete the model, venv or project
media simply because an Azure architecture has been documented.

Potential benefits of eventual removal: recover approximately 9.74 GiB in this
workspace and remove platform-specific CUDA installation/maintenance. Removal
does **not** remove old generated assets or shrink Azure storage automatically.

## Reviewable cleanup order

1. Meet every Azure/model quality, license, privacy, estimate, recovery and
   rollback gate in [13_model_cleanup_plan.md](./13_model_cleanup_plan.md).
2. Remove local generation from application defaults and all callers in a
   tested, separately reviewed code change. Keep read support for historical
   animation metadata and video files.
3. Verify no active jobs or supported project workflow depends on the worker;
   verify configured custom paths before any deletion.
4. Back up or preserve any model files required by the license or rollback plan.
   Obtain explicit approval to remove the exact two repository-local paths.
5. Delete only the specifically approved model directory and isolated worker
   virtual environment. Do not clear global caches or remove `backend\storage`
   project assets.
6. Re-measure disk usage and run backend, frontend and migration tests. Update
   this report with the actual removal date and measured result only after
   deletion is separately authorized and completed.

This report is an inventory and proposed sequence, not approval to perform any
cleanup.
