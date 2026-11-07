from models.models import Project, Scene


class StoryMemoryService:
    def context(self, project: Project, scene: Scene | None = None) -> dict:
        scenes = sorted(project.scenes, key=lambda item: item.scene_number)
        index = scenes.index(scene) if scene in scenes else len(scenes)
        from services.scene_continuity_service import SceneContinuityService
        return {
            "title": project.title, "story_bible": project.story_summary,
            "genre": project.genre, "audience":project.target_audience, "acts": project.three_act_structure,
            "character_bible": [
                {"name": item.name, "role": item.role, "motivations": item.motivations,
                 "relationships": item.relationships, "appearance": item.appearance,
                 "facial_features": item.facial_features, "clothing": item.clothing,
                 "age": item.age, "distinctive_traits": item.distinctive_traits}
                for item in project.characters
            ],
            "scene_history": [
                {"id": item.id, "order": item.scene_number, "event": item.description,
                 "location_and_visuals": item.visual_description,
                 "approved_image": item.image_path if item.approved and item.scene_number < (scene.scene_number if scene else 0) else None}
                for item in scenes
            ],
            "previous_events": [item.description for item in scenes[:index]],
            "current_event": scene.description if scene else None,
            "upcoming_events": [item.description for item in scenes[index+1:]],
            "timeline": [item.id for item in scenes],
            "scene_bridge": SceneContinuityService().bridge(project, scene) if scene else None,
        }
