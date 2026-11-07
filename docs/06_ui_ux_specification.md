# UI / UX Specification — Phase 2

## Design Philosophy

The [local animation extension](./13_local_animation_extension.md) adds per-scene
Timeline estimate/approval, local GPU progress, preview, and explicit clip selection.
Unsupported text-motion controls and non-commercial licensing are visible.
Render displays beat/bridge/camera/transition/animation plans; selected stale or
missing clips block readiness. Input upload supports documents and timestamp
transcription, superseding equal-time segmentation/deferred-only copy below.

No provider request starts without prior estimate approval. A bounded automatic
stage approval on Plan authorizes all missing portraits on Characters, all missing
scene images on Scenes, and sequential local clips on Render. Primary progression
is Plan -> Story -> Characters -> Scenes -> Timeline -> Render. Each asset requires
review; only regeneration needs a per-asset generation action. Failed batches stop
until explicit retry. Narration/speech and export keep separate approvals.
Before approval, display estimated cost, duration, model usage, API-call count,
remaining project budget, and a clear action. Estimates are not provider quotes.
Show actual progress/errors; do not imply success on failure.

New-project and prompt-editor duration controls use integer seconds. Plan offers a
confirmed full prompt restart; Dashboard offers project deletion; Video offers
export/checkpoint deletion. Active jobs block destructive actions. Render defaults
to actual local motion and requires every clip to be approved. Explicit still-image
mode warns that it will not invoke the local model. Video discloses saved source
mode and generated-motion duration, including final-frame holds.

## Routes

### `/`

Redirect to `/docs`: product, workflow/stages, requirements, limitations, cost philosophy, and navigation to projects/new project/settings. Project selection exposes all project routes.

### `/dashboard`

Project list, create-project action, and a persistent `/settings/ai` link. Explain that OpenAI calls require the user's server-side key.

### `/settings/ai`

Fields: provider, text model, image model, default project budget, and default wait time. Show whether `OPENAI_API_KEY` is configured, but never render or persist its value. Saving settings must not call a provider.

### `/projects/new`

Fields: story idea, target length, max budget, and max wait. Populate budget/wait from saved AI defaults. Creating a project must not generate anything; continue to the estimate-first planning page.

### `/projects/{projectId}/analysis`

Before planning: show story/character/scene estimates with total and per-stage cost, duration, model usage, and calls; require an explicit “Generate Story Bible” action. Show waiting progress and provider errors. After generation: show title, summary, genre, audience, acts, character/scene counts, cumulative estimated spend, and a separate total image estimate.

### `/projects/{projectId}/story`

Review/edit story title, genre, audience, summary, three acts, character information, and scene outline. Show the complete planning estimate before “Regenerate Story Bible.” Save edits without invoking a provider.

### `/projects/{projectId}/characters`

Show every character-bible field and portrait prompt. Show one-image cost, duration, image model, and API-call estimate before each portrait/regeneration action. Display image progress, approval state, and actionable errors.

### `/projects/{projectId}/scenes`

Show scene number/title, description, visual description, prompt, estimated duration, image, and status. Show a per-image estimate before each generation/regeneration action; include image-count progress, loading state, and errors.

## Phase 1 Legacy Routes

The existing `/projects/{projectId}/generate` and `/video` pages remain legacy Phase 1 functionality. Phase 2 does not extend them; all text/image provider costs remain separate from local MP4 export costs.

## Common States

- Initial data load and long operations: meaningful label plus rotating humorous workflow messages. At least 20 unique messages per catalogue; shuffle without repetition until exhausted; locale-keyed catalogue for future translations.
- Provider request: disabled duplicate action plus operation-specific progress label.
- Error: visible alert with server message and retry path; never report completion on provider failure.
- Budget limit: disable or reject generation and explain the remaining-budget shortfall.
- Mobile: project navigation remains horizontally scrollable and estimate cards stack without hiding model usage.

## Phase 3 Production Extension

The project navigation now continues **Scenes -> Timeline -> Render -> Your video**. `/generate` redirects to the render approval route; it does not start work.

- `/projects/{projectId}/timeline`: scene image, narration, audio preview, duration, and order. Explicit separate narration and speech estimate approval checkboxes. Move up/down and duration controls; persist with Save. Dirty edits must be saved before generating/rendering. Missing/stale media and remaining budget are visible.
- `/projects/{projectId}/render`: show estimated render cost/runtime/storage/audio duration/video length and cumulative reserved AI estimates before an explicit approval checkbox. No automatic render on navigation. Start, progress percentage/current stage/completed scenes, actionable failure, Resume unchanged render, and Watch/download after success.
- `/projects/{projectId}/video`: playable MP4, attachment download, measured audio duration, timeline video length, file size, render execution time, local render estimate, and cumulative AI estimate. Label provider invoices unavailable. Keep earlier successful output accessible during replacement/recovery.

See [user workflow](./11_user_workflow.md). Historical Phase 2 exclusions above apply to Phase 2 only.

## Phase 3 quality UX

- Review/approval and forward navigation actions are right-aligned; backward navigation remains on the left. Separate save, approve, and approve-and-continue actions retain their distinct behavior.
- Character/scene cards show titles and artwork by default. Expand **details and review** to read identity/prompts and use regeneration/approval controls. Story text, act structure, draft character/scene editors, timeline narration/timing controls, guide sections and extensive source/estimate explanations are collapsible. Key costs, consent checkboxes, readiness blockers and active progress remain visible.
- Funny loading messages include a visible spinning wheel with an accessible status label; reduced-motion preference slows the wheel. Final rendering shows a decimal percentage bar, current stage, elapsed seconds and approximate remaining seconds based on actual FFmpeg progress, never simulated completion.

- Every project page displays current page/stage, local readiness score, story/character/scene approval counts, incomplete files/narration and required actions. Scores explicitly do not measure visual identity.
- Saving a story is not approval. **Save and explicitly approve story** binds approval to the reviewed revision; substantive edits reset approval. Character cards expose identity fields, reference count and local consistency coverage during approval.
- Skipped story/character/scene reviews show an accessible modal with stage, consequences, action, Cancel and Continue Anyway. Cancellation makes no paid retry. Tokens are state-bound and never bypass missing media or spending safeguards.
- `/projects/{projectId}/inputs`: heuristic classification with correction, mixed inputs, captions for images, optional original audio and separate transcription estimate/approval. Preview the adaptive workflow before import. Import is only allowed before planning, to avoid destructive replacement.
- Timeline shows camera/pacing/focus, editable camera/transition, and deferred animation/movement instructions. Only camera effects execute. Saving reordering marks the connected narration/audio stale; restore supplied narration or regenerate the arc before rendering. Historical Phase 2 exclusions above apply to Phase 2 only.
