# UI / UX Specification — Phase 2

## Design Philosophy

No provider request starts automatically. Before each request, display estimated cost, duration, model usage, API-call count, remaining project budget, and a clear generation action. Estimates are labeled as planning estimates, not provider quotes. Show loading/progress and the actual error; do not imply success on failure.

## Routes

### `/`

Landing page with links to the studio and new project.

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

- Initial data load: labeled spinner/skeleton.
- Provider request: disabled duplicate action plus operation-specific progress label.
- Error: visible alert with server message and retry path; never report completion on provider failure.
- Budget limit: disable or reject generation and explain the remaining-budget shortfall.
- Mobile: project navigation remains horizontally scrollable and estimate cards stack without hiding model usage.
