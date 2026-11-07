import math
from pathlib import Path
import subprocess

from services.video_service import VideoService
from schemas.quality import MotionPlan


class VideoComposerService:
    width = 1280
    height = 720
    fps = 24

    def __init__(self) -> None:
        self.ffmpeg = VideoService().ffmpeg

    def _run(self, arguments: list[str], timeout: int = 1800, *, progress_path: Path | None = None) -> str:
        tracking = []
        if progress_path:
            progress_path.unlink(missing_ok=True)
            tracking = ["-progress", str(progress_path), "-stats_period", "0.25"]
        result = subprocess.run(
            [self.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", *tracking, *arguments],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode:
            raise RuntimeError(f"FFmpeg failed: {result.stderr[-2000:]}")
        return result.stderr

    def validate(self, path: Path) -> None:
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError("FFmpeg output is missing or empty.")
        self._run(["-xerror", "-i", str(path), "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"])

    def validate_visual(self, path: Path) -> None:
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError("Generated animation is missing or empty.")
        self._run(["-xerror", "-i", str(path), "-map", "0:v:0", "-f", "null", "-"])

    def animated_segment(self, clip: Path, audio: Path, seconds: int, output: Path, tail: float = 0,
                         *, progress_path: Path | None = None) -> None:
        self.validate_visual(clip)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(".partial.mp4")
        duration = seconds + tail
        try:
            self._run([
                "-y", "-i", str(clip), "-i", str(audio),
                "-map", "0:v:0", "-map", "1:a:0",
                "-vf", (
                    f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
                    f"crop={self.width}:{self.height},setsar=1,fps={self.fps},"
                    f"tpad=stop_mode=clone:stop_duration={duration},format=yuv420p"
                ),
                "-af", f"apad,atrim=duration={duration},asetpts=PTS-STARTPTS",
                "-t", str(duration), "-r", str(self.fps),
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-threads", "2",
                "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
                "-movflags", "+faststart", str(temporary),
            ], progress_path=progress_path)
            self.validate(temporary)
            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)

    def segment(self, image: Path, audio: Path, seconds: int, output: Path, index: int,
                plan: MotionPlan | None = None, tail: float = 0,
                *, progress_path: Path | None = None) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(".partial.mp4")
        frames = math.ceil((seconds + tail) * self.fps)
        x = "(iw-iw/zoom)*on/" + str(max(1, frames - 1))
        if index % 2:
            x = "(iw-iw/zoom)*(1-on/" + str(max(1, frames - 1)) + ")"
        fade = min(0.35, seconds / 4)
        filters = (
            f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
            f"crop={self.width}:{self.height},setsar=1,"
            f"zoompan=z='1.02+0.08*on/{frames}':x='{x}':y='(ih-ih/zoom)/2':"
            f"d={frames}:s={self.width}x{self.height}:fps={self.fps},"
            f"fade=t=in:st=0:d={fade},fade=t=out:st={seconds-fade}:d={fade},format=yuv420p"
        )
        if plan is not None:
            speed = {"reflective":0.04, "balanced":0.08, "urgent":0.12}[plan.pacing]
            zoom = f"1.02+{speed}*on/{frames}" if plan.camera != "pan" else "1.12"
            focus_x = f"(iw-iw/zoom)*{plan.focus_x}"
            if plan.camera == "pan":
                focus_x = f"(iw-iw/zoom)*({plan.focus_x}*(1-on/{frames})+{1-plan.focus_x}*on/{frames})"
            focus_y = f"(ih-ih/zoom)*{plan.focus_y}"
            filters = (
                f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
                f"crop={self.width}:{self.height},setsar=1,"
                f"zoompan=z='{zoom}':x='{focus_x}':y='{focus_y}':"
                f"d={frames}:s={self.width}x{self.height}:fps={self.fps},format=yuv420p"
            )
            if plan.camera == "parallax":
                # Two copies at different scales/speeds simulate planes, not inferred depth or animation.
                filters += (
                    f",split[back][front];[back]boxblur=12:2[blurred];"
                    f"[front]scale={int(self.width*0.9)//2*2}:{int(self.height*0.9)//2*2}[plane];"
                    f"[blurred][plane]overlay=x='(W-w)/2+8*sin(t/3)':y='(H-h)/2',format=yuv420p"
                )
        try:
            self._run([
                "-y", "-i", str(image), "-i", str(audio),
                "-vf", filters, "-af", f"apad,atrim=duration={seconds+tail},asetpts=PTS-STARTPTS",
                "-t", str(seconds+tail), "-r", str(self.fps),
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                "-threads", "2", "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
                "-movflags", "+faststart", str(temporary),
            ], progress_path=progress_path)
            self.validate(temporary)
            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)

    def combine(self, segments: list[Path], output: Path,
                plans: list[MotionPlan] | None = None, durations: list[int] | None = None,
                *, progress_path: Path | None = None) -> None:
        if plans and durations and len(segments)>1:
            self._combine_transitions(segments, output, plans, durations, progress_path=progress_path)
            return
        listing = output.with_suffix(".concat.txt")
        temporary = output.with_suffix(".partial.mp4")
        listing.write_text(
            "".join("file '" + path.resolve().as_posix().replace("'", "'\\''") + "'\n" for path in segments),
            encoding="utf-8",
        )
        try:
            self._run([
                "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                "-c", "copy", "-movflags", "+faststart", str(temporary),
            ], progress_path=progress_path)
            self.validate(temporary)
            temporary.replace(output)
        finally:
            listing.unlink(missing_ok=True)
            temporary.unlink(missing_ok=True)

    def _combine_transitions(self, segments: list[Path], output: Path,
                             plans: list[MotionPlan], durations: list[int],
                             *, progress_path: Path | None = None) -> None:
        temporary = output.with_suffix(".partial.mp4")
        command = ["-y", "-filter_complex_threads", "1"]
        filters = []
        for index,path in enumerate(segments):
            command.extend(["-i",str(path)])
            filters.append(f"[{index}:v]settb=AVTB,setpts=PTS-STARTPTS[v{index}]")
            filters.append(f"[{index}:a]atrim=duration={durations[index]},asetpts=PTS-STARTPTS[a{index}]")
        previous = "v0"
        offset = 0
        for index in range(1,len(segments)):
            offset += durations[index-1]
            plan = plans[index-1]
            transition = {
                "cross_fade":"fade", "fade_black":"fadeblack", "fade_color":"fadewhite",
                "motion_blur":"hblur",
            }[plan.transition]
            if plan.transition == "fade_color" and plan.color == "black":
                transition = "fadeblack"
            target = f"mix{index}"
            filters.append(f"[{previous}][v{index}]xfade=transition={transition}:duration=0.5:offset={offset}[{target}]")
            previous = target
        filters.append("".join(f"[a{index}]" for index in range(len(segments)))+f"concat=n={len(segments)}:v=0:a=1[audio]")
        command.extend([
            "-filter_complex",";".join(filters),"-map",f"[{previous}]","-map","[audio]",
            "-t",str(sum(durations)),"-r",str(self.fps),"-c:v","libx264","-preset","fast",
            "-crf","20","-threads","2","-c:a","aac","-b:a","160k","-pix_fmt","yuv420p",
            "-movflags","+faststart",str(temporary),
        ])
        try:
            self._run(command, progress_path=progress_path)
            self.validate(temporary)
            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)
