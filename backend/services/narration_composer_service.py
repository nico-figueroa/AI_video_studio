from models.models import Project
from schemas.quality import NarrativeArc
from services.ai.providers.base import AIProvider, AIProviderError
from services.character_memory_service import CharacterMemoryService
from services.story_memory_service import StoryMemoryService
from services.timeline_service import fingerprint


class NarrationComposerService:
    def context(self, project: Project) -> dict:
        return {
            "story": StoryMemoryService().context(project),
            "characters": CharacterMemoryService().context(project),
            "scenes": [
                {"scene_id": item.id, "title": item.title, "description": item.description,
                 "beat_number": item.beat_number,
                 "bridge": StoryMemoryService().context(project, item)["scene_bridge"],
                 "maximum_words": min(600, max(5, int(item.estimated_duration * 2.2)))}
                for item in sorted(project.scenes, key=lambda item: item.scene_number)
            ],
        }

    def revision(self, project: Project) -> str:
        # Exclude audio-driven duration changes and image approvals from narrative continuity.
        context = self.context(project)
        return fingerprint([
            project.title, project.story_summary, project.genre, project.target_audience, project.three_act_structure,
            [{key: value for key, value in item.items() if key != "reference_image_paths"}
             for item in context["characters"]["characters"]],
            [[item.id, item.scene_number, item.title, item.description, item.visual_description] for item in sorted(project.scenes, key=lambda item: item.scene_number)],
        ])

    def compose(self, project: Project, provider: AIProvider) -> NarrativeArc:
        arc = provider.compose_narration(self.context(project))
        ids = [item.id for item in sorted(project.scenes, key=lambda item: item.scene_number)]
        if [item.scene_id for item in arc.scenes] != ids:
            raise AIProviderError("Narration must include every scene exactly once in timeline order.")
        if any(not item.text.strip() for item in arc.scenes):
            raise AIProviderError("Narration cannot contain empty scenes.")
        if any(not item.bridge.strip() for item in arc.scenes[1:]):
            raise AIProviderError("Every scene after the opening requires a narrative bridge.")
        if any(not value.strip() for value in (arc.opening,arc.development,arc.resolution)):
            raise AIProviderError("Narration requires an opening, development and resolution.")
        return arc
