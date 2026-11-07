import gc
import json
import os
from pathlib import Path
import shutil
import subprocess

from services.ai.providers.animation import AnimationProvider
from services.ai.providers.base import AIProviderConfigurationError, AIProviderError


MODEL_ID = "stabilityai/stable-video-diffusion-img2vid"
MODEL_REVISION = "9cf024d5bfa8f56622af86c884f26a52f6676f2e"
ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT.parent / "workers" / "local_animation"
RESERVE_BYTES = 15 * 1024**3
LIMITATIONS = (
    "Experimental local SVD: 14 generated frames, no text-directed motion, "
    "no guaranteed blinking/walking/gestures or identity consistency. "
    "Clips shorter than a scene hold their last frame; original narration is retained. "
    "No provider fee; electricity/hardware excluded. Non-commercial use only in this deployment."
)


def require_disk_space(path: Path, additional_bytes: int = 1024**3) -> None:
    probe = path.resolve()
    while not probe.exists():
        probe = probe.parent
    if shutil.disk_usage(probe).free < RESERVE_BYTES + additional_bytes:
        raise AIProviderConfigurationError(
            "Local animation would violate the 15 GiB free-space reserve. Free more disk space."
        )


def require_license() -> None:
    if os.getenv("LOCAL_ANIMATION_LICENSE_ACCEPTED") != "non-commercial":
        raise AIProviderConfigurationError(
            "Local SVD is disabled. Review the Stability AI Community License and set "
            "LOCAL_ANIMATION_LICENSE_ACCEPTED=non-commercial only for authorized non-commercial use."
        )


class LocalSVDProvider(AnimationProvider):
    model = MODEL_ID

    @property
    def python(self) -> Path:
        default = RUNTIME / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        return Path(os.getenv("LOCAL_ANIMATION_PYTHON", str(default)))

    @property
    def model_directory(self) -> Path:
        return Path(os.getenv("LOCAL_ANIMATION_MODEL_DIR", str(RUNTIME / "model")))

    def check_ready(self) -> None:
        require_license()
        if not self.python.is_file() or not (self.model_directory / "model_index.json").is_file():
            raise AIProviderConfigurationError(
                "Local SVD runtime/model is missing. Follow the local animation deployment guide."
            )
        require_disk_space(self.model_directory)

    def estimate_animation_cost(self) -> dict:
        return {
            "provider_cost": 0.0, "runtime_seconds": 900, "storage_mb": 100,
            "model": MODEL_ID, "limitations": LIMITATIONS,
        }

    def generate_scene_animation(self, image: Path, output: Path, *, seed: int = 42) -> dict:
        self.check_ready()
        require_disk_space(output)
        result = subprocess.run(
            [str(self.python), str(RUNTIME / "worker.py"), "generate",
             "--image", str(image.resolve()), "--output", str(output.resolve()), "--seed", str(seed),
             "--model-directory", str(self.model_directory.resolve())],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=1920,
            env={**os.environ, "PYTHONUTF8": "1", "HF_HUB_OFFLINE": "1"},
        )
        if result.returncode:
            raise AIProviderError(f"Local SVD generation failed: {result.stderr[-1800:]}")
        if not output.is_file():
            raise AIProviderError("Local SVD did not produce its requested clip.")
        return json.loads(result.stdout.strip().splitlines()[-1])

    def generate_character_motion(self, reference: Path, output: Path, *, seed: int = 42) -> dict:
        return self.generate_scene_animation(reference, output, seed=seed)

    def generate_transition_animation(self, *args, **kwargs):
        raise AIProviderError(
            "SVD does not support directed transition generation. Use the reviewed FFmpeg transition plan."
        )


def run_inference(image: Path, output: Path, model_directory: Path, seed: int) -> dict:
    """Runs only in the isolated GPU subprocess; imports never load CUDA into the web server."""
    import time
    import torch
    from diffusers import StableVideoDiffusionPipeline
    from diffusers.utils import export_to_video
    from PIL import Image, ImageOps

    require_license()
    require_disk_space(output)
    if not torch.cuda.is_available():
        raise AIProviderConfigurationError("A CUDA-capable NVIDIA GPU is required; CPU fallback is disabled.")
    started = time.monotonic()
    pipeline = None
    temporary = output.with_suffix(".partial.mp4")
    progress = output.with_suffix(".progress.json")
    def report(value: int) -> None:
        progress_temporary = progress.with_suffix(".tmp")
        progress_temporary.write_text(json.dumps({"progress": value}), encoding="utf-8")
        progress_temporary.replace(progress)
    def on_step_end(pipe, step: int, timestep, callback_kwargs: dict):
        require_disk_space(output, 0)
        report(10 + round(80 * (step+1)/15))
        return callback_kwargs
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        report(5)
        pipeline = StableVideoDiffusionPipeline.from_pretrained(
            str(model_directory), torch_dtype=torch.float16, variant="fp16",
            local_files_only=True,
        )
        pipeline.enable_sequential_cpu_offload()
        pipeline.unet.enable_forward_chunking()
        pipeline.set_attention_slice("max")
        with Image.open(image) as source:
            frame = ImageOps.fit(source.convert("RGB"), (512, 288))
        with torch.inference_mode():
            frames = pipeline(
                frame, height=288, width=512, num_frames=14, num_inference_steps=15,
                decode_chunk_size=1, generator=torch.Generator("cpu").manual_seed(seed),
                motion_bucket_id=80, noise_aug_strength=0.02, fps=7,
                callback_on_step_end=on_step_end,
            ).frames[0]
        export_to_video(frames, str(temporary), fps=7)
        require_disk_space(output, 0)
        temporary.replace(output)
        report(95)
        return {
            "model": MODEL_ID, "revision": MODEL_REVISION, "seed": seed,
            "frames": len(frames), "fps": 7, "duration_seconds": len(frames) / 7,
            "width": 512, "height": 288, "steps": 15,
            "execution_seconds": round(time.monotonic() - started, 2),
            "peak_vram_bytes": torch.cuda.max_memory_allocated(),
            "limitations": LIMITATIONS, "license_use": "non-commercial",
        }
    finally:
        temporary.unlink(missing_ok=True)
        del pipeline
        gc.collect()
        torch.cuda.empty_cache()
