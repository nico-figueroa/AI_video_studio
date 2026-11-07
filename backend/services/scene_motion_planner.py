from models.models import Project, Scene
from schemas.quality import MotionPlan


class SceneMotionPlanner:
    def plan(self, project: Project, scene: Scene) -> MotionPlan:
        tone = (project.genre + " " + scene.description).lower()
        urgent = any(word in tone for word in ("action", "chase", "battle", "thriller"))
        reflective = any(word in tone for word in ("quiet", "memory", "reflect", "drama"))
        return MotionPlan(
            camera="pan" if urgent else "slow_zoom" if reflective else "parallax",
            transition="motion_blur" if urgent else "fade_black" if reflective else "cross_fade",
            pacing="urgent" if urgent else "reflective" if reflective else "balanced",
            focus_x=0.4 if scene.scene_number % 2 else 0.6,
            animation_instructions=f"Deferred animation: preserve identity and scene geography for {scene.title}.",
            motion_prompt=f"Maintain {project.genre or 'cinematic'} tone. {scene.visual_description}",
            character_movement_prompt="Subtle motivated gestures only; preserve clothing, age and distinctive traits. Execution deferred.",
        )

    def get(self, project: Project, scene: Scene) -> MotionPlan:
        return MotionPlan.model_validate(scene.motion_plan) if scene.motion_plan else self.plan(project, scene)
