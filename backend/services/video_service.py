import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

from database import STORAGE_DIR
from models.models import Project, Scene
from services.image_service import public_asset_url


class VideoService:
    def __init__(self):
        configured = os.getenv("IMAGEIO_FFMPEG_EXE")
        if configured:
            if not Path(configured).is_file():
                raise RuntimeError("IMAGEIO_FFMPEG_EXE does not point to an existing file.")
            self.ffmpeg = configured
            return

        binary_dir = Path(imageio_ffmpeg.__file__).parent / "binaries"
        bundled = sorted(binary_dir.glob("ffmpeg-*"))
        system_binary = shutil.which("ffmpeg")
        if bundled:
            self.ffmpeg = str(bundled[0])
        elif system_binary:
            self.ffmpeg = system_binary
        else:
            raise RuntimeError("FFmpeg is unavailable. Reinstall imageio-ffmpeg or configure IMAGEIO_FFMPEG_EXE.")

    @staticmethod
    def _ensure_thumbnail(scene: Scene, project_id: int, index: int) -> Path:
        if scene.image_path:
            expected = STORAGE_DIR / "projects" / str(project_id) / f"scene-{scene.id}.png"
            if expected.exists():
                return expected

        output = STORAGE_DIR / "projects" / str(project_id) / f"scene-{scene.id}.png"
        output.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (1280, 720), (14, 23 + index * 6, 43 + index * 8))
        draw = ImageDraw.Draw(image)
        draw.ellipse((760 - index * 14, 60, 1360 - index * 14, 660), fill=(39 + index * 10, 123, 132 + index * 9))
        draw.text((72, 526), scene.title, font=ImageFont.load_default(), fill=(245, 248, 255))
        draw.text((72, 575), "AI VIDEO STUDIO  /  LOCAL PLACEHOLDER ART", fill=(167, 183, 208))
        image.save(output, format="PNG")
        scene.image_path = public_asset_url(output)
        scene.status = "generated"
        return output

    def compose(self, project: Project, scenes: list[Scene], duration_minutes: int) -> Path:
        if not scenes:
            raise ValueError("A story must include at least one scene before export.")

        images = [
            self._ensure_thumbnail(scene, project.id, index)
            for index, scene in enumerate(scenes)
        ]
        output = STORAGE_DIR / "projects" / str(project.id) / f"video-{uuid4().hex}.mp4"
        output.parent.mkdir(parents=True, exist_ok=True)
        seconds_per_scene = duration_minutes * 60 / len(images)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".txt", delete=False, dir=output.parent
        ) as listing:
            for image in images:
                escaped = image.as_posix().replace("'", "'\\''")
                listing.write(f"file '{escaped}'\n")
                listing.write(f"duration {seconds_per_scene}\n")
            escaped = images[-1].as_posix().replace("'", "'\\''")
            listing.write(f"file '{escaped}'\n")
            listing_path = Path(listing.name)

        try:
            command = [
                self.ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(listing_path),
                "-vf",
                "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
                "-r",
                "12",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-movflags",
                "+faststart",
                "-t",
                str(duration_minutes * 60),
                str(output),
            ]
            result = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode:
                raise RuntimeError(f"FFmpeg video export failed: {result.stderr[-2000:]}")
        except (OSError, subprocess.SubprocessError, RuntimeError):
            output.unlink(missing_ok=True)
            raise
        finally:
            listing_path.unlink(missing_ok=True)
        return output

    @staticmethod
    def url(path: Path) -> str:
        return public_asset_url(path)
