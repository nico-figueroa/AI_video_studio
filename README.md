# AI Video Studio

A local-first prototype for taking a story idea through a human-reviewed storyboard to a downloadable MP4. It makes the production estimate visible before approval and enforces the project's budget and wait-time caps.

## What works in the MVP

- Create and analyze projects, with a generated story outline, character bible, scene breakdown, and Economy/Balanced/Premium estimates.
- Edit and save the story and scene descriptions; approve characters, generate local placeholder portraits, and generate/regenerate/approve scene images.
- Select a plan only when it stays within the project limits, track the local video-export job, watch the slideshow MP4, and download it.
- SQLite persistence and local file storage; image generation is behind an `ImageGenerationProvider` interface for a future FLUX integration.

The story and artwork are deterministic prototype placeholders, not output from an AI model. Plan costs, GPU minutes, and times are illustrative provider-equivalent estimates. No paid provider is connected and actual provider spend is **$0**. MP4 export runs locally using the bundled `imageio-ffmpeg` binary.

## Run locally

Use Python 3.10+ and Node.js 20+. Run these in separate terminals from the repository root.

### Backend

```powershell
python -m pip install -r backend\requirements.txt
Set-Location backend
python -m uvicorn main:app --reload
```

The API is at `http://localhost:8000`; interactive API documentation is at `http://localhost:8000/docs`. SQLite data, generated images, and MP4s are stored under `backend\storage`.

On the first start after upgrading, data in the old `backend\database\storage` location is copied to `backend\storage`; the old files are left untouched as a backup. Stop any older backend process before starting the migration. If the new storage directory already exists without a database, move or back it up first so migration cannot overwrite it.

Run only one backend process against a storage directory: exports use in-process background tasks, and startup marks unfinished jobs as failed so they can be retried. Generated project media is served under `/storage/projects`; the SQLite database is not served.

Browser mutation requests must come from an allowed origin. The defaults are the localhost frontend on port 3000 and the backend API documentation on port 8000. Set `STUDIO_FRONTEND_ORIGINS` to a comma-separated list of trusted frontend origins if needed; this also configures CORS. Command-line clients without an `Origin` header remain supported. Bind this local prototype only to trusted interfaces.

### Frontend

```powershell
Set-Location frontend
npm install
npm run dev
```

Open `http://localhost:3000`. To use another API origin, set `NEXT_PUBLIC_API_URL` before starting Next.js.

## Verify

```powershell
python -m pytest tests
Set-Location frontend
npm run typecheck
npm run build
```

Backend tests use a temporary database and media directory and do not modify the application's storage.

## Layout

- `backend/api`, `backend/schemas`, `backend/services`, `backend/repositories`, `backend/models`, `backend/database`: typed FastAPI application layers.
- `tests`: backend API and end-to-end video export tests.
- `frontend/app`: Next.js App Router landing, dashboard, and project workflow pages.
- `frontend/components`, `frontend/services`: reusable UI and typed API client.
- `backend/storage`: local SQLite database and generated artifacts (created at runtime, ignored by Git).

# AI Video Studio Principles

1. No hidden costs.

2. No generation before estimation.

3. Users approve spending before execution.

4. Every workflow displays expected time.

5. Every workflow displays expected quality.

6. Users can stop and resume generation.

7. Users own their generated assets.

8. Resource consumption should be visible.

9. Model selection should be transparent.

10. The platform succeeds when users achieve their goal, not when they consume more credits.