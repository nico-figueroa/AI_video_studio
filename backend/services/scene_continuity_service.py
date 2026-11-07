class SceneContinuityService:
    @staticmethod
    def bridge(project, scene) -> dict:
        scenes = sorted(project.scenes, key=lambda item: item.scene_number)
        index = scenes.index(scene)
        def context(item):
            return {
                "scene_id": item.id, "title": item.title, "events": item.description,
                "location_objects_and_visuals": item.visual_description,
            } if item else None
        return {
            "previous": context(scenes[index-1] if index else None),
            "current": context(scene),
            "next": context(scenes[index+1] if index+1 < len(scenes) else None),
            "characters": [item.name for item in project.characters],
            "instructions": "Preserve established geography, props, identity and causal event order; review changes explicitly.",
        }

    def film_plan(self, project) -> dict:
        from services.scene_motion_planner import SceneMotionPlanner
        from services.story_segmentation_service import StorySegmentationService
        return {
            "narrative": StorySegmentationService.describe(project),
            "scenes": [
                {"scene_id": scene.id, "beat_number": scene.beat_number,
                 "bridge": self.bridge(project, scene),
                 "camera_motion_transition_animation_plan": SceneMotionPlanner().get(project, scene).model_dump(),
                 "animation_capability": "Optional experimental SVD image-to-video; text-directed motion unsupported."}
                for scene in sorted(project.scenes, key=lambda item: item.scene_number)
            ],
        }
