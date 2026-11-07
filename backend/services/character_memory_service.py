import json
import shutil
from pathlib import Path

from models.models import Character, Project, Scene
from services.timeline_service import fingerprint, local_media


class CharacterMemoryService:
    @staticmethod
    def memory(character: Character) -> dict:
        return {
            "id": character.id, "name": character.name, "role": character.role,
            "appearance": character.appearance, "clothing": character.clothing,
            "age": character.age, "distinctive_traits": character.distinctive_traits,
            "portrait_prompt": character.portrait_prompt, "negative_prompt": character.negative_prompt,
            "personality": character.personality, "description": character.description,
            "motivations":character.motivations,"relationships":character.relationships,
            "facial_features": character.facial_features,
            "reference_image_paths": character.reference_image_paths,
        }

    def context(self, project: Project) -> dict:
        return {"characters": [self.memory(item) for item in project.characters],
                "prompt_package_policy": "Preserve facial features, clothing, age and distinctive traits from approved references."}

    def references(self, project: Project, scene: Scene | None = None) -> list[Path]:
        paths = []
        for character in project.characters:
            for url in character.reference_image_paths:
                path = local_media(project.id, url)
                if path not in paths:
                    paths.append(path)
        if scene is not None:
            previous = next((item for item in sorted(project.scenes, key=lambda item: item.scene_number, reverse=True)
                             if item.scene_number < scene.scene_number and item.approved and item.image_path), None)
            if previous:
                paths = paths[:5] + [local_media(project.id, previous.image_path)]
        return paths[:6]

    def approve_reference(self, character: Character) -> None:
        if not character.image_path:
            return
        source = local_media(character.project_id, character.image_path)
        digest = fingerprint(source.read_bytes().hex())[:16]
        destination = source.with_name(f"reference-{character.id}-{digest}.png")
        if source != destination and not destination.exists():
            shutil.copy2(source, destination)
        from services.image_service import public_asset_url
        url = public_asset_url(destination)
        character.reference_image_paths = list(dict.fromkeys([*character.reference_image_paths, url]))[-6:]

    def prompt(self, project: Project, prompt: str) -> str:
        return prompt + "\nCHARACTER MEMORY (keep identity, clothing and traits unchanged):\n" + json.dumps(self.context(project), ensure_ascii=True)
