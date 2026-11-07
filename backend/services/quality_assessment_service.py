from pathlib import Path
from sqlalchemy.orm import object_session

from models.models import Project
from schemas.quality import QualityReport, ReviewState
from services.character_memory_service import CharacterMemoryService
from services.narration_composer_service import NarrationComposerService
from services.story_memory_service import StoryMemoryService
from services.timeline_service import fingerprint, local_media
from services.workflow_service import story_revision


class QualityAssessmentService:
    @staticmethod
    def exists(project: Project, url: str | None) -> bool:
        if not url:
            return False
        from fastapi import HTTPException
        try:
            local_media(project.id, url)
            return True
        except HTTPException:
            return False

    def assess(self, project: Project) -> QualityReport:
        scenes = sorted(project.scenes, key=lambda item: item.scene_number)
        chars = project.characters
        revision = NarrationComposerService().revision(project)
        reviews = [
            ReviewState(stage="story", approved=int(project.story_approved), total=1, required_action="Save edits and explicitly approve the Story Bible."),
            ReviewState(stage="characters", approved=sum(item.approved for item in chars), total=len(chars), required_action="Generate/review and approve each character portrait."),
            ReviewState(stage="scenes", approved=sum(item.approved for item in scenes), total=len(scenes), required_action="Generate/review and approve each scene image."),
        ]
        blockers = []
        if not project.story_approved:
            blockers.append("Story review is incomplete.")
        if not chars or not all(item.approved for item in chars):
            blockers.append("Character reviews are incomplete.")
        if not scenes or not all(item.approved for item in scenes):
            blockers.append("Scene reviews are incomplete.")
        memory_hash = fingerprint(CharacterMemoryService().context(project))
        char_scores = []
        character_scores = {}
        for item in chars:
            fields = (item.name, item.role, item.appearance, item.clothing, item.age, item.distinctive_traits, item.facial_features, item.portrait_prompt, item.negative_prompt)
            coverage = sum(bool(field.strip()) for field in fields) / len(fields)
            references = any(self.exists(project, path) for path in item.reference_image_paths)
            char_scores.append(coverage * 70 + int(references) * 30)
            character_scores[item.id] = round(char_scores[-1])
        narration = []
        continuity = []
        assets = [int(self.exists(project,item.image_path)) for item in chars]
        require_animation = project.generation_approval.get("render_mode", "local_animation") == "local_animation"
        animation_approved = 0
        for item in chars:
            if not self.exists(project,item.image_path):
                blockers.append(f"Character {item.name}: portrait file is missing.")
        for scene in scenes:
            db = object_session(project)
            if db is not None:
                from services.animation_service import animation_problem, selected_animation
                selected = selected_animation(db, scene)
                if selected:
                    issue = animation_problem(project, scene, selected)
                    assets.append(int(not issue))
                    if issue:
                        blockers.append(f"Scene {scene.scene_number}: {issue}")
                    elif require_animation:
                        animation_approved += 1
                if require_animation and not selected:
                    blockers.append(f"Scene {scene.scene_number}: local model clip is missing or not approved. Generate/review it on Render.")
                    assets.append(0)
            item = scene.narration
            current = item is not None and item.source_hash == fingerprint([scene.id, revision])
            if project.input_manifest.get("preserve_narration") and item is not None:
                # Imported scripts are tied to the same whole-project continuity revision.
                current = item.source_hash == fingerprint([scene.id, revision])
            audio = bool(current and item is not None and item.audio_path and Path(item.audio_path).is_file())
            narration.append(int(bool(current and item is not None and (scene.scene_number == 1 or item.transition_text or project.input_manifest.get("preserve_narration")))))
            context = scene.generation_context
            continuity.append(int(
                context.get("character_hash") == memory_hash
                and context.get("story_hash") == fingerprint(StoryMemoryService().context(project, scene))
            ))
            assets.extend([int(self.exists(project, scene.image_path)), int(bool(current)), int(audio)])
            if not current:
                blockers.append(f"Scene {scene.scene_number}: narration is missing or outdated.")
            if not audio:
                blockers.append(f"Scene {scene.scene_number}: narration audio is missing or outdated.")
            if not self.exists(project, scene.image_path):
                blockers.append(f"Scene {scene.scene_number}: image file is missing.")
        if require_animation:
            reviews.append(ReviewState(stage="animations", approved=animation_approved, total=len(scenes),
                                       required_action="Generate all local clips on Render, then preview and approve every scene clip."))
        def percent(values: list[int]) -> int:
            return round(sum(values) / len(values) * 100) if values else 0
        dimensions = {
            "character_consistency": round(sum(char_scores) / len(char_scores)) if char_scores else 0,
            "narrative_continuity": percent(narration),
            "scene_continuity": percent(continuity),
            "asset_completeness": percent(assets),
            "approval_coverage": round(sum(item.approved for item in reviews) / max(1, sum(item.total for item in reviews)) * 100),
        }
        return QualityReport(
            score=round(sum(dimensions.values()) / len(dimensions)), dimensions=dimensions,
            blockers=blockers, reviews=reviews, story_revision=story_revision(project), stage=project.status,
            character_scores=character_scores,
        )
