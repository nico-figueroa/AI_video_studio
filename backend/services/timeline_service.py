import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException

from models.models import Scene
from repositories.production_repository import ProductionRepository
from schemas.production import TimelineItem, TimelineOut, TimelineUpdate
from services.image_service import public_asset_url
from services.project_service import ProjectService
import services.image_service as media


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def scene_source(scene: Scene) -> str:
    return fingerprint([scene.title, scene.description])


def local_media(project_id: int, url: str) -> Path:
    prefix = f"/storage/projects/{project_id}/"
    path = urlsplit(url).path
    if not path.startswith(prefix):
        raise HTTPException(status_code=409, detail="Invalid project media path.")
    root = (media.STORAGE_DIR / "projects" / str(project_id)).resolve()
    result = (root / path[len(prefix):]).resolve()
    if not result.is_relative_to(root) or not result.is_file():
        raise HTTPException(status_code=409, detail="Project media is missing. Regenerate the asset.")
    return result


class TimelineService:
    def __init__(self, repository: ProductionRepository):
        self.repository = repository

    def get(self, project_id: int) -> TimelineOut:
        project = ProjectService(self.repository).get(project_id)
        from services.narration_composer_service import NarrationComposerService
        from services.scene_motion_planner import SceneMotionPlanner
        arc_revision = NarrationComposerService().revision(project)
        narrations = {item.scene_id: item for item in self.repository.narrations(project_id)}
        items = []
        sources = []
        for scene in sorted(project.scenes, key=lambda item: item.scene_number):
            from services.animation_service import animation_problem, selected_animation
            animation = selected_animation(self.repository.db, scene)
            animation_issue = None
            animation_url = None
            if animation:
                animation_issue = animation_problem(project, scene, animation)
                if not animation_issue:
                    animation_url = public_asset_url(Path(animation.clip_path))
            narration = narrations.get(scene.id)
            if narration is not None and narration.source_hash != fingerprint([scene.id, arc_revision]):
                narration = None
            audio_seconds = narration.audio_seconds if narration is not None else None
            minimum = math.ceil((audio_seconds or 0) + 0.25)
            duration = max(scene.estimated_duration, minimum)
            image_exists = False
            audio_exists = False
            if scene.image_path:
                try:
                    local_media(project_id, scene.image_path)
                    image_exists = True
                except HTTPException:
                    image_exists = False
            if narration is not None and narration.audio_path:
                audio_exists = Path(narration.audio_path).is_file()
            items.append(TimelineItem(
                scene_id=scene.id, order=scene.scene_number, title=scene.title,
                image_url=scene.image_path, narration=narration.text if narration is not None else None,
                audio_url=public_asset_url(Path(narration.audio_path)) if narration is not None and narration.audio_path else None,
                audio_seconds=audio_seconds, duration_seconds=duration,
                ready=bool(scene.approved and image_exists and narration is not None and audio_exists and not animation_issue),
                motion_plan=SceneMotionPlanner().get(project, scene),
                animation_url=animation_url, animation_issue=animation_issue,
            ))
            sources.append([scene.id, scene_source(scene), scene.approved, scene.beat_number])
        revision = fingerprint([sources, [item.model_dump() for item in items]])
        return TimelineOut(
            project_id=project_id, revision=revision, scenes=items,
            duration_seconds=sum(item.duration_seconds for item in items),
            ready=bool(items) and all(item.ready for item in items),
        )

    def update(self, project_id: int, payload: TimelineUpdate) -> TimelineOut:
        self.repository.begin_write()
        self.repository.lock_project(project_id)
        self.repository.require_no_active_job(project_id)
        timeline = self.get(project_id)
        if payload.revision != timeline.revision:
            raise HTTPException(status_code=409, detail="Timeline changed. Reload before saving.")
        ids = [item.scene_id for item in payload.scenes]
        if len(set(ids)) != len(ids) or set(ids) != {item.scene_id for item in timeline.scenes}:
            raise HTTPException(status_code=422, detail="Include each project scene exactly once.")
        project = ProjectService(self.repository).get(project_id)
        existing = {scene.id: scene for scene in project.scenes}
        if ids != [item.scene_id for item in timeline.scenes]:
            project.story_approved = False
            project.narrative_analysis = {}
        minimums = {item.scene_id: math.ceil((item.audio_seconds or 0) + 0.25) for item in timeline.scenes}
        for item in payload.scenes:
            if item.duration_seconds < minimums[item.scene_id]:
                raise HTTPException(status_code=422, detail="Scene duration cannot truncate its narration.")
        # Two flushes avoid transient conflicts with the unique scene-number constraint.
        for index, scene in enumerate(existing.values(), start=1):
            scene.scene_number = -index
        self.repository.db.flush()
        for index, item in enumerate(payload.scenes, start=1):
            existing[item.scene_id].scene_number = index
            existing[item.scene_id].estimated_duration = item.duration_seconds
        self.repository.save()
        return self.get(project_id)
