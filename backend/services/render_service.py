import logging
import shutil
import time
import subprocess
from datetime import timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from models.models import RenderJob, Video, utc_now
from repositories.production_repository import ProductionRepository
from schemas.production import ProductionEstimate, ProductionVideo, RenderRequest, RenderStatus, TimelineOut, VideoChapter
from services.image_service import public_asset_url
from services.project_service import ProjectService
from services.timeline_service import TimelineService, fingerprint, local_media
from services.video_composer_service import VideoComposerService
from services.workflow_service import WorkflowService
from schemas.stage_generation import RenderMode
import services.image_service as media

logger = logging.getLogger(__name__)


class RenderService:
    def __init__(self, repository: ProductionRepository):
        self.repository = repository

    def estimate(self, project_id: int, mode: RenderMode = "local_animation") -> ProductionEstimate:
        timeline = TimelineService(self.repository).get(project_id)
        seconds = timeline.duration_seconds
        return ProductionEstimate(
            estimate_id=fingerprint(["render", timeline.revision, "720p-local-animation-v4", mode]),
            estimated_cost=0, estimated_runtime_seconds=max(5, seconds * 1.6 + len(timeline.scenes) * 2),
            # Output (~4 Mbps) plus resumable segments and temporary final export.
            estimated_storage_mb=round(seconds * 0.55 * 3, 2),
            estimated_audio_seconds=round(sum(item.audio_seconds or 0 for item in timeline.scenes), 2),
            estimated_video_seconds=seconds, estimated_api_calls=0,
            model_usage=("Reviewed local SVD clips" if mode == "local_animation" else "Explicit still-image camera effects")
                        + " / FFmpeg / H.264 / AAC / 1280x720 / 24 fps",
            notes=("Final export only; GPU generation is a separate approved stage. Every scene must have a "
                   "current approved local clip in local-animation mode. Clips contain 2 seconds of generated "
                   "motion followed by a final-frame hold, not continuous generated video. No provider fee; "
                   "electricity and hardware excluded."
                   if mode == "local_animation" else
                   "Still-image export: the local video model will NOT be called. Images use FFmpeg camera effects."),
        )

    def start(self, project_id: int, request: RenderRequest, review_override: str = "") -> RenderStatus:
        self.repository.begin_write()
        self.repository.lock_project(project_id)
        self.repository.require_no_active_job(project_id)
        project = ProjectService(self.repository).get(project_id)
        if project.status == "planning":
            raise HTTPException(status_code=409, detail="Wait for story planning to finish.")
        timeline = TimelineService(self.repository).get(project_id)
        if not timeline.ready:
            raise HTTPException(status_code=409, detail="Approve every scene image, generate current narration/audio, and resolve stale or missing selected clips first.")
        if request.mode == "local_animation":
            missing = [item.title for item in timeline.scenes if not item.animation_url]
            if missing:
                raise HTTPException(status_code=409, detail=(
                    "Local-animation export requires a current approved motion clip for EVERY scene. "
                    "Generate the local GPU batch and review its clips first. Missing: " + ", ".join(missing)
                ))
        WorkflowService.require_review(project,"story",review_override)
        WorkflowService.require_review(project,"characters",review_override)
        self.repository.db.flush()
        estimate = self.estimate(project_id, request.mode)
        if request.estimate_id != estimate.estimate_id:
            raise HTTPException(status_code=409, detail="Render estimate changed. Review it and approve again.")
        if estimate.estimated_runtime_seconds > project.max_wait_minutes * 60:
            raise HTTPException(status_code=422, detail="Render estimate exceeds the project wait limit.")
        if shutil.disk_usage(media.STORAGE_DIR).free < estimate.estimated_storage_mb * 1_000_000 + 15 * 1024**3:
            raise HTTPException(status_code=422, detail="Not enough local storage for the estimated render and 15 GiB free-space reserve.")
        if request.resume_job_id:
            job = self.repository.render_job(request.resume_job_id)
            if job is None or job.project_id != project_id:
                raise HTTPException(status_code=404, detail="Render job not found.")
            if job.status != "failed":
                raise HTTPException(status_code=409, detail="Only failed or interrupted renders can be resumed.")
            if job.timeline_hash != timeline.revision:
                raise HTTPException(status_code=409, detail="Timeline changed. Start a new render instead.")
            if job.snapshot.get("mode", "still_images") != request.mode:
                raise HTTPException(status_code=409, detail="Render mode changed. Start a new render instead.")
            job.status = "queued"
            job.error = None
            job.completed_at = None
            job.started_at = None
            job.snapshot = {**job.snapshot, "attempt_start_progress": job.progress, "live_progress": None}
            job.current_stage = "Resuming"
        else:
            from services.scene_continuity_service import SceneContinuityService
            job = RenderJob(
                id=str(uuid4()), project_id=project_id, timeline_hash=timeline.revision,
                snapshot={"timeline": timeline.model_dump(), "estimate": estimate.model_dump(), "mode": request.mode,
                          "film_plan": SceneContinuityService().film_plan(project)},
            )
            self.repository.add(job)
        project.status = "rendering"
        self.repository.save()
        return self.status(project_id)

    def status(self, project_id: int) -> RenderStatus:
        project = ProjectService(self.repository).get(project_id)
        job = self.repository.latest_job(project_id)
        if job is None:
            raise HTTPException(status_code=404, detail="No render has been started.")
        progress = float(job.progress)
        tracking = job.snapshot.get("live_progress")
        if job.status in {"running", "failed"} and tracking:
            path = Path(tracking["path"])
            try:
                with path.open("rb") as stream:
                    stream.seek(max(0, path.stat().st_size - 8192))
                    lines = stream.read().decode("utf-8", errors="replace").splitlines(keepends=True)
            except FileNotFoundError:
                lines = []  # FFmpeg has not created the progress file yet.
            for line in reversed(lines):
                if line.startswith("out_time_us=") and line.endswith("\n"):
                    value = line.partition("=")[2].strip()
                    if not value.isdigit():
                        continue
                    fraction = min(1, int(value) / 1_000_000 / tracking["duration"])
                    progress = max(progress, tracking["base"] + tracking["span"] * fraction)
                    break
        if job.status != "completed":
            progress = min(99, progress)
        elapsed = 0.0
        if job.started_at:
            started = job.started_at.replace(tzinfo=timezone.utc) if job.started_at.tzinfo is None else job.started_at
            finished = job.completed_at or utc_now()
            if finished.tzinfo is None:
                finished = finished.replace(tzinfo=timezone.utc)
            elapsed = max(0, (finished - started).total_seconds())
        remaining = None
        if job.status in {"queued", "running"}:
            estimate = job.snapshot["estimate"]["estimated_runtime_seconds"]
            baseline = job.snapshot.get("attempt_start_progress", 0)
            measured = progress - baseline
            remaining = (elapsed * (100 - progress) / measured if measured >= 1 and elapsed >= 1
                         else max(0, estimate * (100 - baseline) / 100 - elapsed))
            if job.status == "running" and remaining == 0:
                remaining = None
        elif job.status == "completed":
            remaining = 0
        return RenderStatus(
            job_id=job.id, project_id=project_id, status=job.status, progress=round(progress, 1),
            current_stage=job.current_stage, error=job.error, completed_scenes=job.completed_scenes,
            video_url=public_asset_url(Path(project.video_path)) if job.status == "completed" and project.video_path else None,
            elapsed_seconds=round(elapsed, 1),
            estimated_remaining_seconds=round(remaining, 1) if remaining is not None else None,
        )

    def run(self, job_id: str) -> None:
        self.repository.begin_write()
        job = self.repository.render_job(job_id)
        if job is None:
            raise RuntimeError(f"Render job {job_id} does not exist.")
        self.repository.lock_project(job.project_id)
        self.repository.db.refresh(job)
        if job.status != "queued":
            self.repository.db.rollback()
            return
        job.status = "running"
        job.started_at = job.started_at or utc_now()
        job.snapshot = {**job.snapshot, "attempt_start_progress": job.progress}
        job.current_stage = "Preparing timeline"
        self.repository.save()
        started = time.monotonic()
        previous_seconds = job.execution_seconds
        try:
            composer = VideoComposerService()
            timeline = TimelineOut.model_validate(job.snapshot["timeline"])
            directory = media.STORAGE_DIR / "projects" / str(job.project_id) / f"render-{job.id}"
            directory.mkdir(parents=True, exist_ok=True)
            paths = []
            completed_seconds = 0
            for index, scene in enumerate(timeline.scenes):
                path = directory / f"scene-{scene.scene_id}.mp4"
                paths.append(path)
                job.current_stage = f"Composing scene {index+1}/{len(timeline.scenes)}"
                progress_path = directory / f"scene-{scene.scene_id}.progress"
                progress_path.unlink(missing_ok=True)
                tail = 0.5 if index < len(timeline.scenes)-1 else 0
                job.snapshot = {**job.snapshot, "live_progress": {
                    "path": str(progress_path), "base": 80 * completed_seconds / timeline.duration_seconds,
                    "span": 80 * scene.duration_seconds / timeline.duration_seconds,
                    "duration": scene.duration_seconds + tail,
                }}
                self.repository.save()
                if scene.scene_id in job.completed_scenes and path.is_file():
                    try:
                        composer.validate(path)
                    except (RuntimeError, OSError):
                        logger.warning("Rebuilding damaged render checkpoint %s", path, exc_info=True)
                        path.unlink(missing_ok=True)
                if not path.is_file():
                    if not scene.image_url or not scene.audio_url:
                        raise RuntimeError("The render snapshot is missing scene media.")
                    if job.snapshot.get("mode") == "local_animation":
                        if not scene.animation_url:
                            raise RuntimeError("Local-animation snapshot has no approved clip; refusing a still-image fallback.")
                        composer.animated_segment(
                            local_media(job.project_id, scene.animation_url),
                            local_media(job.project_id, scene.audio_url),
                            scene.duration_seconds, path, tail=tail, progress_path=progress_path,
                        )
                    else:
                        composer.segment(
                            local_media(job.project_id, scene.image_url),
                            local_media(job.project_id, scene.audio_url),
                            scene.duration_seconds, path, index, plan=scene.motion_plan, tail=tail,
                            progress_path=progress_path,
                        )
                job.completed_scenes = [item.scene_id for item in timeline.scenes[:index+1]]
                completed_seconds += scene.duration_seconds
                job.progress = max(job.progress, round(80 * completed_seconds / timeline.duration_seconds))
                job.execution_seconds = round(previous_seconds + time.monotonic() - started, 3)
                self.repository.save()
            job.current_stage = "Combining and validating MP4"
            job.progress = max(job.progress, 80)
            progress_path = directory / "final.progress"
            progress_path.unlink(missing_ok=True)
            job.snapshot = {**job.snapshot, "live_progress": {
                "path": str(progress_path), "base": 80, "span": 19, "duration": timeline.duration_seconds,
            }}
            self.repository.save()
            output = directory.parent / f"video-{job.id}.mp4"
            composer.combine(paths, output,
                             plans=[item.motion_plan for item in timeline.scenes],
                             durations=[item.duration_seconds for item in timeline.scenes],
                             progress_path=progress_path)
            job.execution_seconds = round(previous_seconds + time.monotonic() - started, 3)
            project = ProjectService(self.repository).get(job.project_id)
            self.repository.add(Video(
                project_id=job.project_id, render_job_id=job.id, file_path=str(output),
                duration_seconds=timeline.duration_seconds,
                audio_seconds=sum(item.audio_seconds or 0 for item in timeline.scenes),
                size_bytes=output.stat().st_size, generation_seconds=job.execution_seconds,
                estimated_cost=job.snapshot["estimate"]["estimated_cost"],
            ))
            project.video_path = str(output)
            project.status = "completed"
            self.repository.add_asset(project_id=job.project_id, asset_type="video", file_path=str(output))
            job.status = "completed"
            job.current_stage = "MP4 ready"
            job.progress = 100
            job.completed_at = utc_now()
            self.repository.save()
        except Exception as error:
            logger.exception("Render %s failed", job_id)
            self.repository.db.rollback()
            job = self.repository.render_job(job_id)
            if job is None:
                raise
            job.status = "failed"
            job.current_stage = "Render failed"
            job.error = str(error)[:2000]
            job.execution_seconds = round(previous_seconds + time.monotonic() - started, 3)
            job.completed_at = utc_now()
            ProjectService(self.repository).get(job.project_id).status = "render_failed"
            self.repository.save()

    def video(self, project_id: int) -> ProductionVideo:
        project = ProjectService(self.repository).get(project_id)
        if not project.video_path or not Path(project.video_path).is_file():
            raise HTTPException(status_code=404, detail="This project does not have an exported video yet.")
        video = self.repository.latest_video(project_id)
        result = ProductionVideo(
            url=public_asset_url(Path(project.video_path)),
            download_url=f"/api/v1/projects/{project_id}/video/download",
            estimated_ai_spend=project.estimated_spend,
        )
        if video and video.file_path == project.video_path:
            result.duration_seconds = video.duration_seconds
            result.audio_seconds = video.audio_seconds
            result.size_bytes = video.size_bytes
            result.generation_seconds = video.generation_seconds
            result.estimated_cost = video.estimated_cost
            result.render_job_id = video.render_job_id
            result.playback_audio_url = f"/api/v1/projects/{project_id}/video/audio?render_job_id={video.render_job_id}"
            job = self.repository.render_job(video.render_job_id)
            if job:
                scenes = job.snapshot["timeline"]["scenes"]
                result.render_mode = job.snapshot.get("mode", "legacy_reviewed_sources")
                offset = 0
                for scene in scenes:
                    motion = (min(2, scene["duration_seconds"])
                              if result.render_mode != "still_images" and scene.get("animation_url") else 0)
                    result.chapters.append(VideoChapter(
                        scene_id=scene["scene_id"], title=scene["title"], start_seconds=offset,
                        duration_seconds=scene["duration_seconds"], generated_motion_seconds=motion,
                    ))
                    offset += scene["duration_seconds"]
                if result.render_mode != "still_images":
                    animated = [scene for scene in scenes if scene.get("animation_url")]
                    result.animated_scene_count = len(animated)
                    result.generated_motion_seconds = sum(min(2, scene["duration_seconds"]) for scene in animated)
        return result

    def playback_audio(self, project_id: int, render_job_id: str) -> Path:
        self.repository.begin_write()
        self.repository.lock_project(project_id)
        video = self.video(project_id)
        if video.render_job_id != render_job_id:
            raise HTTPException(status_code=409, detail="The published video changed. Reload the player before listening.")
        source = local_media(project_id, video.url)
        directory = source.parent / f"render-{render_job_id}"
        if directory.is_symlink() or directory.resolve() != directory.absolute():
            raise HTTPException(status_code=409, detail="Unsafe render media path; playback audio requires manual review.")
        output = directory / "playback.wav"
        if output.is_symlink():
            raise HTTPException(status_code=409, detail="Unsafe playback audio path; manual review is required.")
        if output.is_file():
            return output
        required = (video.duration_seconds or 0) * 16000 * 2
        if shutil.disk_usage(media.STORAGE_DIR).free < required + 15 * 1024**3:
            raise HTTPException(status_code=422, detail="Not enough storage for browser audio and the 15 GiB reserve.")
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory / f"playback-{uuid4().hex}.wav"
        try:
            VideoComposerService()._run([
                "-y", "-i", str(source), "-map", "0:a:0", "-vn", "-c:a", "pcm_s16le",
                "-ar", "16000", "-ac", "1", str(temporary),
            ])
            temporary.replace(output)
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
            logger.exception("Browser audio extraction failed for render %s", render_job_id)
            raise HTTPException(status_code=500, detail="Could not prepare browser narration audio. Try downloading the MP4.") from error
        finally:
            temporary.unlink(missing_ok=True)
        return output
