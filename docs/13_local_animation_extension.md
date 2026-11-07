# Phase 3 local animation and narrative extension

## Scope and honest capability boundary

This extends Phase 3, not Phase 4. Local image-to-video runs on the user's GPU;
there is no paid animation API, cloud deployment, GPU rental or always-on worker.
Text, images, speech and timestamp transcription still use the existing configured
AI provider and their separate approval/budget gates.

**Powered by Stability AI.** The current local adapter is
`stabilityai/stable-video-diffusion-img2vid`, pinned to revision
`9cf024d5bfa8f56622af86c884f26a52f6676f2e`.
It generates 14 frames at 512x288, exported at 7 fps (2 seconds), with 15 diffusion
steps. Resolution is deliberately below the training resolution to fit this
machine; it is experimental, not a production-quality promise.

SVD does **not** accept text motion prompts. Blinking, breathing, head movement,
walking, gestures, idle motion, tracking/dolly/follow shots and exact identity
cannot be guaranteed or advertised as implemented controls. Motion instructions
are retained as planning metadata. Directed transition generation explicitly
raises an unsupported-capability error; reviewed transitions execute in FFmpeg.
This adapter is a real generated-motion path, not a claim that every requested
character-animation capability is complete.

## Implemented pipeline

- The primary UI sequence is now Plan -> Story -> Characters -> Scenes -> Timeline
  -> Render. One bounded automatic-generation approval on Plan enables missing
  portrait/scene batches on their stage entry and the sequential local GPU batch
  on Render. Each result still requires preview/approval; failures never retry
  automatically. Per-asset buttons are for explicit regeneration, not required
  initial generation. See [workflow controls](./11_user_workflow.md#corrected-stage-sequence-and-project-controls).
- Local-animation export now explicitly requires a current approved clip for
  every scene. Still-image export is a separate explicit source mode; no silent
  fallback is permitted. The video page displays its persisted source mode,
  generated clip count and actual generated-motion duration.
- Target durations accept integer seconds. Confirmed prompt restart clears the
  full production sequence including supplied inputs, but retains spending.
  Project/video deletion is available with confirmation and active-job guards.
- Migration `0005_workflow` adds fractional-minute duration storage, bounded
  stage consent and checkpointed batch jobs. Use Alembic head as usual.

- OpenAI structured scene planning now decomposes stories into 2-6 narrative
  beats, with 2-4 ordered scenes per beat and at most 12 scenes total.
  `NarrativeAnalysisService` validates/normalizes the hierarchy;
  `StorySegmentationService` exposes its persisted beat metadata. Existing/other
  providers can retain their flat scene plans, explicitly identified as legacy
  grouping rather than semantic beat analysis.
- User-supplied scenes and assets are never expanded or replaced automatically.
  Supplied narration without scenes splits locally at sentence/paragraph
  boundaries, grouped to at most six scenes. Very short supplied material can
  remain one scene. No invented provider paraphrase replaces its words.
- `SceneContinuityService` supplies previous/current/next events, visual location/
  object descriptions and character context. `/film-plan` exposes beat, bridge,
  camera, pacing, transition and animation plans before render. Each render
  snapshot retains this plan.
- Character prompt packages include facial features, appearance, clothing,
  traits, bibles and approved reference files. Scores remain local coverage
  checks, not visual identity verification.
- TXT, MD, DOCX, extractable-text PDF, JSON, YAML and CSV imports are parsed
  locally. Original document files are retained in project media. JSON/YAML use
  the documented input schema; CSV uses character `name` or scene
  `title,description,duration_seconds` columns. Text remains bounded to 6000
  characters; at most 12 scenes/characters/files, 20 MB/file, 40 MB combined.
  Structured files are limited to 1 MB, PDFs to 100 unencrypted pages, and
  DOCX expanded content to 40 MB. No OCR, arbitrary schema inference, YAML
  aliases or executable content is supported.
- Uploaded audio uses separately approved `whisper-1` word timestamps.
  Scene audio boundaries follow actual word timestamps, not equal-time splits;
  leading/trailing silence remains in the first/last slice. Paired scripts must
  align with recognized words or the operation reports an explicit error without
  replacing the script. Existing multi-scene imports without timestamps must
  approve transcription before restoring source slices.
- Timeline offers an estimate, explicit GPU approval, rotating feedback,
  step progress, clip preview and separate render-selection approval. Existing
  still-image rendering remains available by explicit deselection.
- PostgreSQL `animation_jobs` stores immutable input hashes, motion-plan
  snapshots, seed, status/progress, output path, review and result metadata.
  A partial unique index admits one active GPU job globally. Active jobs block
  project mutation/rendering; no duplicate GPU execution is automatically retried.
- Startup marks interrupted jobs failed. Explicit retry creates a new job.
  Source changes or missing selected files block rendering rather than silently
  substituting still images. Prior successful videos are preserved.
- FFmpeg uses selected generated clips, holds the final frame if the scene is
  longer, ignores clip soundtrack audio, retains the complete narration, and
  applies existing transitions. Final output remains H.264/AAC, 720p/24fps;
  upscaling does not create additional source detail.

## Install on Windows

The web application keeps its existing Python interpreter and dependencies.
The GPU worker uses a separate Python 3.12 environment because CUDA/PyTorch
compatibility must not change the main application runtime.

```powershell
py install 3.12
py -3.12 -m venv workers\local_animation\.venv
& .\workers\local_animation\.venv\Scripts\python.exe -m pip install --no-cache-dir -r workers\local_animation\requirements.txt
```

Read the [upstream license](https://huggingface.co/stabilityai/stable-video-diffusion-img2vid/blob/main/LICENSE.md)
and [acceptable-use policy](https://stability.ai/use-policy).
This deployment is enabled for authorized **non-commercial evaluation only**.
Commercial use is not authorized by accepting the non-commercial setting:
review registration/enterprise requirements separately. Do not redistribute
weights without the agreement, required Notice and attribution.

After personally accepting the applicable terms:

```powershell
$env:LOCAL_ANIMATION_LICENSE_ACCEPTED = "non-commercial"
& .\workers\local_animation\.venv\Scripts\python.exe .\workers\local_animation\worker.py download
```

Only the selected FP16 components/configuration and upstream README/license are
downloaded (approximately 4.2 GiB of weights), not all repository variants. There
is no runtime download. Inference uses offline, local files and safetensors;
project images are not uploaded to an external animation service.
Keep `LOCAL_ANIMATION_LICENSE_ACCEPTED=non-commercial` in the root, gitignored
`.env` to enable the backend after restart. Leave it empty to disable generation.

Optional environment overrides: `LOCAL_ANIMATION_PYTHON` and
`LOCAL_ANIMATION_MODEL_DIR` are absolute local paths. Never put model files in
public frontend assets. The virtual environment and model are gitignored.

From `backend`, run `alembic upgrade head` before starting one backend process.
Migration `0004_animation` extends existing projects non-destructively. Rebuild/
restart the frontend when ready; an already-running production frontend will
continue serving its previous build until then.

## Resource and execution safeguards

Download and inference enforce at least 15 GiB remaining on the relevant volume
plus conservative additional space. Diffusion steps recheck the reserve.
Final render approval also reserves 15 GiB in addition to estimated render storage.
Concurrent unrelated disk usage can still consume space; do not treat this as
an operating-system quota. Avoid concurrent GPU-heavy applications.

CUDA inference runs in a short-lived subprocess, not the web server. Sequential
CPU offload, FP16, sliced attention and single-frame decoding limit VRAM use.
There is no silent CPU or still-image fallback after an animation failure.
An internal 30-minute watchdog bounds inference; progress reports generation
steps followed by encoding/validation. Errors and unsupported capabilities remain
visible. Retry requires fresh explicit approval.

Runtime estimate is a conservative 900 seconds per clip, not a guarantee.
Measured on the RTX 2070 Super 8 GiB / 16 GiB RAM machine: the initial fixture
generated 14 nonblack, changing frames in **294.25 seconds** at 512x288.
This is a technical motion/decode benchmark, not a human-character quality test.
The corrected automatic batch -> real model -> clip review -> final MP4 path was
also executed: one synthetic two-second clip completed its batch in **275.63
seconds** (261.19 seconds of model execution), then exported a validated
local-animation H.264/AAC MP4. No paid text/image/speech calls were used in that test.
Local provider cost is $0, excluding hardware/electricity.

## API

- `GET /projects/{id}/scenes/{sceneId}/animation`: current estimate and latest job.
- `POST` same path: `{approved:true, estimate_id, seed:42}`; returns `202` job.
- `PUT .../animation/approval`: `{job_id, approved}`; select/deselect a reviewed
  clip. The job and scene must belong to this project. Missing/stale selections
  can always be deselected when no operation is active.
- `GET /projects/{id}/film-plan`: derived current film/beat/bridge plans.
- Timeline scenes add `animation_url` and `animation_issue`. Selected stale or
  missing clips make `ready:false` and require replacement or explicit deselection.

GET requests never load a model or generate content. GPU approval is separate
from final MP4 render approval. APIs preserve existing review, wait, mutation and
origin safeguards.

## Verification

```powershell
python -m pytest tests\test_animation_extension.py
$env:STUDIO_TEST_POSTGRES = "1"
python -m pytest tests
Remove-Item Env:\STUDIO_TEST_POSTGRES
```

Automated tests use synthetic motion fixtures, not a paid API or automatic GPU
model generation. They verify real clip composition/MP4 decoding, source
staleness, explicit approval, locks, failure reporting, reserve/license gates,
multiple scenes per beat, document formats and unequal timestamp-based audio
ranges. A separately approved local GPU smoke test verifies the installed model.
