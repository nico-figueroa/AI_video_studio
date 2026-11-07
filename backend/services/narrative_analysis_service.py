from schemas.ai_schemas import NarrativeScenePlan, ScenePlan
from services.ai.providers.base import AIProviderError


class NarrativeAnalysisService:
    @staticmethod
    def flatten(plan: NarrativeScenePlan) -> ScenePlan:
        scenes = []
        for beat_number, beat in enumerate(plan.beats, 1):
            for scene in beat.scenes:
                scenes.append(scene.model_copy(update={
                    "scene_number": len(scenes) + 1, "beat_number": beat_number,
                }))
        if len(scenes) > 12:
            raise AIProviderError("Narrative plan exceeds 12 scenes. Use 2-6 beats with 2-4 scenes per beat.")
        return ScenePlan(scenes=scenes)

    @staticmethod
    def store(project, plan: NarrativeScenePlan) -> None:
        project.narrative_analysis = {
            "source": "provider_story_decomposition",
            "beats": [
                {"number": index, **beat.model_dump(exclude={"scenes"})}
                for index, beat in enumerate(plan.beats, 1)
            ],
        }
