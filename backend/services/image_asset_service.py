import json
import logging
from uuid import uuid4

from models.models import Character, Project, Scene
from repositories.project_repository import ProjectRepository
from services.ai.providers.base import AIProvider, AIProviderError
from services.character_memory_service import CharacterMemoryService
from services.story_memory_service import StoryMemoryService
from services.timeline_service import fingerprint
import services.image_service as media

logger = logging.getLogger(__name__)


class ImageAssetService:
    prompt_budget = 30_000

    def __init__(self, repository: ProjectRepository):
        self.repository = repository

    @classmethod
    def image_prompt(cls, text: str, context: dict, story_context: dict | None) -> str:
        # Image conditioning needs identity and adjacent visuals, not repeated copies of every event.
        characters = {
            **context,
            "characters": [
                {key: value for key, value in character.items()
                 if key not in {"personality", "motivations", "relationships", "reference_image_paths"}}
                for character in context["characters"]
            ],
        }
        continuity = ({key: value for key, value in story_context.items()
                       if key not in {"character_bible", "scene_history", "current_event"}}
                      if story_context else None)

        def excerpt(value: object, limit: int) -> object:
            if isinstance(value, str) and len(value) > limit:
                return value[:limit] + " [context excerpt]"
            if isinstance(value, dict):
                return {key: excerpt(item, limit) for key, item in value.items()}
            if isinstance(value, list):
                return [excerpt(item, limit) for item in value]
            return value

        for limit in (None, 2048, 1024, 512, 256, 128):
            identity = characters if limit is None else excerpt(characters, limit)
            story = continuity if limit is None else excerpt(continuity, limit)
            prompt = text + "\nCHARACTER MEMORY (keep identity, clothing and traits unchanged):\n"
            prompt += json.dumps(identity, ensure_ascii=False, separators=(",", ":"))
            if story:
                prompt += "\nSTORY CONTINUITY:\n" + json.dumps(story, ensure_ascii=False, separators=(",", ":"))
            if len(prompt) <= cls.prompt_budget:
                if limit is not None:
                    logger.warning("Image continuity context excerpted to %s characters per field; prompt length %s",
                                   limit, len(prompt))
                return prompt
        raise AIProviderError(
            "Scene/portrait prompt and required continuity exceed the image prompt budget. "
            "Shorten the image prompt or character descriptions before retrying; no image request was sent."
        )

    def generate(self, project: Project, asset: Character | Scene, provider: AIProvider) -> None:
        memory = CharacterMemoryService()
        context = memory.context(project)
        is_scene = isinstance(asset, Scene)
        references = memory.references(project, asset) if is_scene else memory.references(project)
        story_context = StoryMemoryService().context(project, asset) if is_scene else None
        text = ((asset.image_prompt or asset.visual_description or asset.description) if is_scene
                else (asset.portrait_prompt or asset.description))
        prompt = self.image_prompt(text, context, story_context)
        kind = "scene" if is_scene else "character"
        image = provider.generate_consistent_image(
            prompt, media.STORAGE_DIR / "projects" / str(project.id) / f"{kind}-{asset.id}.png", references,
        )
        asset.image_path = f"{media.public_asset_url(image)}?v={uuid4().hex}"
        asset.approved = False
        asset.generation_context = {"character_hash": fingerprint(context), "reference_count": len(references)}
        if is_scene:
            asset.status = "generated"
            asset.generation_context["story_hash"] = fingerprint(story_context)
        self.repository.add_asset(project_id=project.id, asset_type=f"{kind}_image", file_path=str(image))
