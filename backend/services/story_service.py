import re
from pathlib import Path

from database import STORAGE_DIR
from models.models import Character, Project, Scene
from repositories.project_repository import ProjectRepository
from schemas.schemas import MAX_STORY_TITLE_LENGTH


class StoryService:
    def __init__(self, repository: ProjectRepository):
        self.repository = repository

    @staticmethod
    def _title(prompt: str) -> str:
        cleaned = re.sub(r"^[\"']|[\"']$", "", prompt.strip())
        words = re.findall(r"[A-Za-z0-9'-]+", cleaned)
        return " ".join(words[:7]).strip().capitalize()[:MAX_STORY_TITLE_LENGTH] or "An untold story"

    def analyze(self, project: Project, *, refresh: bool = False) -> Project:
        if project.scenes and not refresh:
            return project

        if refresh:
            asset_dir = STORAGE_DIR / "projects" / str(project.id)
            for character in project.characters:
                (asset_dir / f"character-{character.id}.png").unlink(missing_ok=True)
            for scene in project.scenes:
                (asset_dir / f"scene-{scene.id}.png").unlink(missing_ok=True)
            if project.video_path:
                Path(project.video_path).unlink(missing_ok=True)
            project.video_path = None
            project.selected_plan = None
            project.actual_cost = 0
            self.repository.clear_assets(project.id)

        project.characters.clear()
        project.scenes.clear()

        project.title = self._title(project.prompt)
        project.story_summary = (
            f"{project.prompt.strip()} Follow a determined explorer through an unfamiliar world, "
            "where each discovery reveals a deeper mystery and a choice with lasting consequences."
        )
        project.status = "analysis_complete"
        project.characters.extend(
            [
                Character(
                    name="The Explorer",
                    description="A curious, resourceful protagonist whose past gives the journey personal stakes.",
                ),
                Character(
                    name="The Guide",
                    description="A local expert who knows the hidden world but has reasons to keep its secrets.",
                ),
                Character(
                    name="The Guardian",
                    description="A powerful presence protecting the world the protagonist has discovered.",
                ),
            ]
        )

        scene_count = min(8, max(4, project.target_minutes * 2))
        beats = [
            ("The Ordinary World", "Introduce the protagonist, their world, and the unanswered question."),
            ("A Strange Discovery", "An unexpected clue points toward a hidden place and changes everything."),
            ("Crossing the Threshold", "The protagonist commits to the journey and meets an unlikely guide."),
            ("A World Unveiled", "A vivid new world reveals both its wonder and its rules."),
            ("The Cost of Truth", "A revelation puts the mission and a new friendship at risk."),
            ("The Turning Point", "The protagonist makes a difficult choice that changes the balance."),
            ("The Final Test", "The guardian and the protagonist meet in a decisive confrontation."),
            ("A New Beginning", "The discovery reshapes the future and leaves one last mystery."),
        ]
        for number, (title, beat) in enumerate(beats[:scene_count], start=1):
            project.scenes.append(Scene(
                scene_number=number,
                title=title,
                description=f"{beat} Story idea: {project.prompt}",
                status="pending",
            ))

        return project

    def update(self, project: Project, title: str, summary: str, characters: list, scenes: list) -> None:
        project.title = title
        project.story_summary = summary
        project.status = "story_reviewed"
        existing_characters = {character.id: character for character in project.characters}
        for item in characters:
            character = existing_characters.get(item.id)
            if character is not None:
                if character.name != item.name or character.description != item.description:
                    character.image_path = None
                    character.approved = False
                character.name = item.name
                character.description = item.description

        existing_scenes = {scene.id: scene for scene in project.scenes}
        for item in scenes:
            scene = existing_scenes.get(item.id)
            if scene is not None:
                if scene.title != item.title or scene.description != item.description:
                    scene.image_path = None
                    scene.approved = False
                    scene.status = "pending"
                scene.title = item.title
                scene.description = item.description

        self.repository.save()
