from models.models import Character, Project, Scene
from repositories.project_repository import ProjectRepository
from schemas.ai_schemas import CharacterBibleData, ScenePlanData
from services.ai.providers.base import AIProvider, AIProviderError
from services.scene_motion_planner import SceneMotionPlanner


class StoryService:
    def __init__(self, repository: ProjectRepository):
        self.repository = repository

    def analyze(
        self, project: Project, provider: AIProvider, *, refresh: bool = False
    ) -> Project:
        if project.scenes and not refresh:
            return project

        story = provider.generate_story(project.prompt, project.target_minutes)
        characters = provider.generate_character_bible(story)
        if not characters.characters:
            raise AIProviderError("The provider returned an empty character bible.")
        from services.narrative_analysis_service import NarrativeAnalysisService
        narrative = provider.generate_narrative_plan(story, characters, project.target_minutes)
        scene_plan = (NarrativeAnalysisService.flatten(narrative) if narrative else
                      provider.generate_scene_plan(story, characters, project.target_minutes))
        if not 4 <= len(scene_plan.scenes) <= 12:
            raise AIProviderError("The provider must return between 4 and 12 planned scenes.")

        if refresh:
            project.video_path = None
            project.selected_plan = None
            project.actual_cost = 0
            self.repository.clear_assets(project.id)

        project.characters.clear()
        project.scenes.clear()
        self.repository.db.flush()

        project.title = story.title
        project.story_summary = story.summary
        project.genre = story.genre
        project.target_audience = story.target_audience
        project.three_act_structure = story.three_act_structure.model_dump()
        project.status = "analysis_complete"
        project.story_approved = False
        project.narration_arc = {}
        project.narrative_analysis = {}
        if narrative:
            NarrativeAnalysisService.store(project, narrative)
        project.characters.extend(self._character_model(item) for item in characters.characters)
        project.scenes.extend(
            self._scene_model(item, index)
            for index, item in enumerate(scene_plan.scenes, start=1)
        )
        for scene in project.scenes:
            scene.motion_plan = SceneMotionPlanner().plan(project, scene).model_dump()

        return project

    @staticmethod
    def _character_model(item: CharacterBibleData) -> Character:
        description = item.personality.strip() or item.appearance.strip() or item.role.strip()
        return Character(
            name=item.name,
            description=description,
            role=item.role,
            personality=item.personality,
            appearance=item.appearance,
            motivations=item.motivations,
            relationships=item.relationships,
            portrait_prompt=item.portrait_prompt,
            clothing=item.clothing, age=item.age, distinctive_traits=item.distinctive_traits,
            negative_prompt=item.negative_prompt,
            facial_features=item.facial_features,
        )

    @staticmethod
    def _scene_model(item: ScenePlanData, number: int) -> Scene:
        return Scene(
            scene_number=number,
            title=item.scene_title,
            description=item.scene_description,
            visual_description=item.visual_description,
            image_prompt=item.image_prompt,
            estimated_duration=item.estimated_duration,
            status="pending",
            beat_number=item.beat_number,
        )

    def update(
        self,
        project: Project,
        title: str,
        summary: str,
        genre: str,
        target_audience: str,
        three_act_structure: dict[str, str],
        characters: list,
        scenes: list,
    ) -> str:
        content_changed = (
            project.title != title or project.story_summary != summary or project.genre != genre
            or project.target_audience != target_audience or project.three_act_structure != three_act_structure
        )
        if {item.id for item in characters} != {item.id for item in project.characters} or len(characters) != len(project.characters):
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail="Include each character exactly once.")
        if {item.id for item in scenes} != {item.id for item in project.scenes} or len(scenes) != len(project.scenes):
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail="Include each scene exactly once.")
        project.title = title
        project.story_summary = summary
        project.genre = genre
        project.target_audience = target_audience
        project.three_act_structure = three_act_structure
        project.status = "story_reviewed"
        existing_characters = {character.id: character for character in project.characters}
        for item in characters:
            character = existing_characters.get(item.id)
            if character is not None:
                portrait_details_changed = any(
                    getattr(character, field) != getattr(item, field)
                    for field in ("name", "description", "appearance")
                )
                portrait_prompt_changed = item.portrait_prompt != character.portrait_prompt
                if any(getattr(character,field)!=getattr(item,field) for field in ("role","personality","motivations","relationships")):
                    content_changed = True
                portrait_fields = (
                    "name", "description", "appearance", "portrait_prompt", "clothing", "age",
                    "distinctive_traits", "negative_prompt", "facial_features",
                )
                if any(getattr(character, field) != getattr(item, field) for field in portrait_fields):
                    character.image_path = None
                    character.approved = False
                    content_changed = True
                    character.reference_image_paths = []
                for field in (
                    "name", "description", "role", "personality", "appearance",
                    "motivations", "relationships", "portrait_prompt",
                    "clothing", "age", "distinctive_traits", "negative_prompt", "facial_features",
                ):
                    setattr(character, field, getattr(item, field))
                if portrait_details_changed and not portrait_prompt_changed:
                    character.portrait_prompt = (
                        " ".join(
                            detail.strip()
                            for detail in (
                                character.name,
                                character.description,
                                character.appearance,
                            )
                            if detail.strip()
                        )
                    )

        existing_scenes = {scene.id: scene for scene in project.scenes}
        for item in scenes:
            scene = existing_scenes.get(item.id)
            if scene is not None:
                image_details_changed = any(
                    getattr(scene, field) != getattr(item, field)
                    for field in ("title", "description", "visual_description")
                )
                image_prompt_changed = item.image_prompt != scene.image_prompt
                if any(
                    getattr(scene, field) != getattr(item, field)
                    for field in ("title", "description", "visual_description", "image_prompt")
                ):
                    scene.image_path = None
                    scene.approved = False
                    scene.status = "pending"
                    content_changed = True
                for field in (
                    "title", "description", "visual_description", "image_prompt",
                    "estimated_duration",
                ):
                    setattr(scene, field, getattr(item, field))
                if image_details_changed and not image_prompt_changed:
                    scene.image_prompt = (
                        " ".join(
                            detail.strip()
                            for detail in (
                                scene.title,
                                scene.description,
                                scene.visual_description,
                            )
                            if detail.strip()
                        )
                    )

        if content_changed:
            project.story_approved = False
            project.narrative_analysis = {}
        from services.workflow_service import story_revision
        revision = story_revision(project)
        self.repository.save()
        return revision
