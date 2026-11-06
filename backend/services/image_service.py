import hashlib
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from database import STORAGE_DIR
from models.models import Character, Scene


class ImageGenerationProvider:
    def generate_scene(self, scene: Scene, project_id: int, variation: str = "") -> Path:
        raise NotImplementedError

    def generate_character(self, character: Character, project_id: int, variation: str = "") -> Path:
        raise NotImplementedError


class PlaceholderImageProvider(ImageGenerationProvider):
    """Local deterministic artwork; replace this provider to integrate FLUX or another model."""

    @staticmethod
    def _render(text: str, subtitle: str, output: Path, seed: str) -> Path:
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        colors = [
            (digest[0] // 2, digest[1] // 2, digest[2] // 2),
            (digest[3] // 2, digest[4] // 2, digest[5] // 2),
            (digest[6] // 2, digest[7] // 2, digest[8] // 2),
        ]
        image = Image.new("RGB", (1280, 720))
        draw = ImageDraw.Draw(image)
        for y in range(720):
            ratio = y / 720
            color = tuple(int(colors[0][i] * (1 - ratio) + colors[1][i] * ratio) for i in range(3))
            draw.line((0, y, 1280, y), fill=color)
        draw.ellipse((785, 70, 1450, 735), fill=colors[2])
        draw.ellipse((870, 155, 1360, 645), fill=colors[1])
        draw.rounded_rectangle((64, 482, 920, 660), radius=24, fill=(8, 15, 29))
        font = ImageFont.truetype("arial.ttf", 46) if Path("C:/Windows/Fonts/arial.ttf").exists() else ImageFont.load_default()
        safe_title = re.sub(r"\s+", " ", text)[:48]
        draw.text((100, 520), safe_title, font=font, fill=(248, 249, 252))
        draw.text((100, 590), subtitle[:70], font=ImageFont.load_default(), fill=(180, 193, 214))
        output.parent.mkdir(parents=True, exist_ok=True)
        image.save(output, format="PNG")
        return output

    def generate_scene(self, scene: Scene, project_id: int, variation: str = "") -> Path:
        return self._render(
            scene.title,
            "AI VIDEO STUDIO  /  LOCAL PLACEHOLDER ART",
            STORAGE_DIR / "projects" / str(project_id) / f"scene-{scene.id}.png",
            f"{scene.description}{variation}",
        )

    def generate_character(self, character: Character, project_id: int, variation: str = "") -> Path:
        return self._render(
            character.name,
            "CHARACTER REFERENCE  /  LOCAL PLACEHOLDER ART",
            STORAGE_DIR / "projects" / str(project_id) / f"character-{character.id}.png",
            f"{character.description}{variation}",
        )


def public_asset_url(path: Path) -> str:
    return f"/storage/{path.relative_to(STORAGE_DIR).as_posix()}"
