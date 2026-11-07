from fastapi import HTTPException

from models.models import Project, utc_now
from services.timeline_service import fingerprint


def story_revision(project: Project) -> str:
    return fingerprint([
        project.title, project.story_summary, project.genre, project.target_audience, project.three_act_structure,
        [[item.id, item.name, item.description, item.appearance, item.clothing, item.age,
          item.distinctive_traits, item.negative_prompt, item.role, item.personality, item.motivations,
          item.relationships, item.portrait_prompt] for item in project.characters],
        [[item.id, item.scene_number, item.title, item.description, item.visual_description,item.image_prompt] for item in project.scenes],
    ])


class WorkflowService:
    @staticmethod
    def require_review(project: Project, stage: str, override: str = "", *, record: bool = True) -> None:
        ready = {
            "story": bool(project.story_summary and project.story_approved),
            "characters": bool(project.characters) and all(item.approved for item in project.characters),
            "scenes": bool(project.scenes) and all(item.approved for item in project.scenes),
        }[stage]
        if ready:
            return
        token = fingerprint([stage, story_revision(project), [
            [item.id, item.approved, item.image_path]
            for item in (project.characters if stage == "characters" else project.scenes)
        ]])
        if token not in override.split(","):
            raise HTTPException(status_code=409, detail={
                "code": "review_required", "stage": stage, "confirmation_token": token,
                "message": f"You are about to proceed without approving all {stage} content.",
                "consequences": "Unreviewed content can cause inconsistent characters, scenes, or narration and wasted provider spending.",
                "required_action": f"Review and approve {stage}, or explicitly choose Continue Anyway for this request.",
            })
        if record:
            project.review_overrides = (project.review_overrides + [{
                "stage": stage, "revision": token, "at": utc_now().isoformat(),
            }])[-100:]
