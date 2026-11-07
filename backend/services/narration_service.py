import logging
import json
import math
import os
from pathlib import Path
from uuid import uuid4
import wave

from fastapi import HTTPException

from models.models import Narration
from models.models import AIConfiguration, Project
from repositories.production_repository import ProductionRepository
from schemas.production import NarrationItem, NarrationOut, NarrationRequest, ProductionApproval, ProductionEstimate
from services.ai.configuration import create_ai_provider, get_ai_configuration
from services.ai.providers.base import AIProvider, AIProviderError
from services.image_service import public_asset_url
from services.project_service import ProjectService
from services.timeline_service import fingerprint, scene_source, local_media
from services.narration_composer_service import NarrationComposerService
from services.workflow_service import WorkflowService
import services.image_service as media

logger = logging.getLogger(__name__)


def speech_settings() -> tuple[str, str]:
    return (
        os.getenv("OPENAI_SPEECH_MODEL", "gpt-4o-mini-tts"),
        os.getenv("OPENAI_SPEECH_VOICE", "alloy"),
    )


class NarrationService:
    def __init__(self, repository: ProductionRepository):
        self.repository = repository

    def estimates(self, project_id: int) -> tuple[ProductionEstimate, ProductionEstimate]:
        project = ProjectService(self.repository).get(project_id)
        configuration = get_ai_configuration(self.repository.db)
        scenes = sorted(project.scenes, key=lambda item: item.scene_number)
        arc_revision = NarrationComposerService().revision(project)
        stored = {item.scene_id: item for item in self.repository.narrations(project_id)}
        missing_audio = []
        for scene in scenes:
            item = stored.get(scene.id)
            if item is not None and item.source_hash == fingerprint([scene.id, arc_revision]):
                if not item.audio_path or not Path(item.audio_path).is_file():
                    missing_audio.append(item)
        words = sum(min(600, max(5, int(scene.estimated_duration * 2.2))) for scene in scenes)
        text_rate = float(os.getenv("ESTIMATED_TEXT_USD_PER_1K_TOKENS", "0.002"))
        speech_rate = float(os.getenv("ESTIMATED_SPEECH_USD_PER_1K_CHARACTERS", "0.015"))
        source = [[scene.id, scene_source(scene), scene.estimated_duration, scene.approved] for scene in scenes]
        input_tokens = len(json.dumps(NarrationComposerService().context(project))) / 4
        narration_cost = round((input_tokens + words * 1.5 + 300 * len(scenes)) / 1000 * text_rate, 4)
        text = ProductionEstimate(
            estimate_id=fingerprint(["narration", source, arc_revision, configuration.provider, configuration.model, narration_cost]),
            estimated_cost=narration_cost, estimated_runtime_seconds=60 if scenes else 0,
            estimated_storage_mb=round(words * 7 / 1_000_000, 3),
            estimated_audio_seconds=round(words / 2.5, 1),
            estimated_video_seconds=sum(scene.estimated_duration for scene in scenes),
            estimated_api_calls=1 if scenes else 0, model_usage=configuration.model + " / coherent narrative arc",
        )
        if project.input_manifest.get("preserve_narration"):
            text = text.model_copy(update={
                "estimate_id":fingerprint(["supplied-narration",source,arc_revision,project.input_manifest]),
                "estimated_cost":0.0,"estimated_runtime_seconds":0.0,"estimated_api_calls":0,
                "model_usage":"Supplied narration / preserved words / local audio",
            })
        model, voice = speech_settings()
        cost = round(sum(round(len(item.text) / 1000 * speech_rate, 4) for item in missing_audio), 4)
        audio = ProductionEstimate(
            estimate_id=fingerprint(["audio", source, [[item.id, item.text, item.audio_path] for item in missing_audio], configuration.provider, model, voice, cost]),
            estimated_cost=cost, estimated_runtime_seconds=len(missing_audio) * 30,
            estimated_storage_mb=round(sum(item.recommended_seconds for item in missing_audio) * 48000 / 1_000_000, 2),
            estimated_audio_seconds=round(sum(item.recommended_seconds for item in stored.values()), 1),
            estimated_video_seconds=sum(max(scene.estimated_duration, math.ceil(stored[scene.id].recommended_seconds)) if scene.id in stored else scene.estimated_duration for scene in scenes),
            estimated_api_calls=len(missing_audio), model_usage=f"{model} / {voice}",
        )
        if project.input_manifest.get("source_audio"):
            audio = audio.model_copy(update={
                "estimate_id":fingerprint(["supplied-audio",source,arc_revision,[item.id for item in missing_audio]]),
                "estimated_cost":0.0,"estimated_runtime_seconds":5.0 if missing_audio else 0.0,
                "estimated_api_calls":0,"model_usage":"Supplied audio / local restoration / no synthetic voice",
            })
        return text, audio

    def get(self, project_id: int) -> NarrationOut:
        project = ProjectService(self.repository).get(project_id)
        scenes = {scene.id: scene for scene in project.scenes}
        arc_revision = NarrationComposerService().revision(project)
        text_estimate, audio_estimate = self.estimates(project_id)
        return NarrationOut(
            items=[
                NarrationItem(
                    scene_id=item.scene_id, text=item.text,
                    recommended_seconds=item.recommended_seconds,
                    transition_text=item.transition_text,
                    audio_url=public_asset_url(Path(item.audio_path)) if item.audio_path else None,
                    audio_seconds=item.audio_seconds,
                    stale=item.scene_id not in scenes or item.source_hash != fingerprint([item.scene_id, arc_revision]),
                )
                for item in self.repository.narrations(project_id)
            ],
            narration_estimate=text_estimate, audio_estimate=audio_estimate,
        )

    def _begin(
        self, project_id: int, approval: ProductionApproval, operation: str, review_override: str = ""
    ) -> tuple[Project, ProductionEstimate, AIConfiguration, AIProvider | None]:
        self.repository.begin_write()
        self.repository.lock_project(project_id)
        self.repository.require_no_active_job(project_id)
        project = ProjectService(self.repository).get(project_id)
        if project.status == "planning":
            raise HTTPException(status_code=409, detail="Wait for story planning to finish.")
        if not project.scenes or not all(scene.image_path for scene in project.scenes):
            raise HTTPException(status_code=409, detail="Generate every scene image first; missing files cannot be skipped.")
        for scene in project.scenes:
            if scene.image_path:
                local_media(project_id, scene.image_path)
        WorkflowService.require_review(project, "scenes", review_override)
        self.repository.db.flush()
        estimates = self.estimates(project_id)
        estimate = estimates[0 if operation == "narrating" else 1]
        if approval.estimate_id != estimate.estimate_id:
            raise HTTPException(status_code=409, detail="Estimate changed. Review the latest estimate.")
        if estimate.estimated_runtime_seconds > project.max_wait_minutes * 60:
            raise HTTPException(status_code=422, detail="Generation exceeds the project wait limit.")
        if round(project.estimated_spend + estimate.estimated_cost, 4) > project.max_budget:
            raise HTTPException(status_code=422, detail="Generation exceeds the remaining project budget.")
        configuration = get_ai_configuration(self.repository.db)
        local_source = (
            operation=="narrating" and project.input_manifest.get("preserve_narration")
            or operation=="generating_audio" and project.input_manifest.get("source_audio")
        )
        provider = None if local_source else create_ai_provider(configuration)
        return project, estimate, configuration, provider

    def generate(self, project_id: int, approval: NarrationRequest, review_override: str = "") -> NarrationOut:
        project, estimate, configuration, provider = self._begin(project_id, approval, "narrating", review_override)
        previous = {item.scene_id: item for item in self.repository.narrations(project_id)}
        if previous and not approval.regenerate:
            raise HTTPException(status_code=409, detail="Narration exists. Explicitly approve regeneration.")
        ProjectService._reserve_estimated_cost(project, estimate.estimated_cost)
        project.status = "narrating"
        self.repository.save()
        try:
            if project.input_manifest.get("preserve_narration"):
                from services.input_analysis_service import InputAnalysisService
                source = project.input_manifest.get("transcript") or project.input_manifest.get("text")
                if not source:
                    raise HTTPException(status_code=409,detail="Supplied narration text is missing.")
                InputAnalysisService(self.repository).attach_supplied_narration(project, source)
                project.status = "narration_ready"
                self.repository.save()
                return self.get(project_id)
            if provider is None:
                raise RuntimeError("Narration provider is not configured.")
            composer = NarrationComposerService()
            arc = composer.compose(project, provider)
            arc_revision = composer.revision(project)
            generated = {item.scene_id: item for item in arc.scenes}
            for scene in sorted(project.scenes, key=lambda item: item.scene_number):
                part = generated[scene.id]
                text = " ".join(piece.strip() for piece in (part.bridge, part.text) if piece.strip())
                if not text or len(text) > 4000:
                    raise AIProviderError("The provider returned empty or oversized narration.")
                item = previous.get(scene.id)
                if item is None:
                    item = Narration(project_id=project_id, scene_id=scene.id)
                    self.repository.add(item)
                item.text = text
                item.transition_text = part.bridge
                item.source_hash = fingerprint([scene.id, arc_revision])
                item.recommended_seconds = round(len(text.split()) / 2.5 + 0.5, 2)
                item.provider = configuration.provider
                item.model = configuration.model
                item.audio_path = None
                item.audio_seconds = None
                item.speech_model = None
                item.voice = None
            project.narration_arc = arc.model_dump()
            project.status = "narration_ready"
            self.repository.save()
        except Exception:
            logger.exception("Narration generation failed for project %s", project_id)
            self._fail(project_id)
            raise
        return self.get(project_id)

    def generate_audio(self, project_id: int, approval: ProductionApproval, review_override: str = "") -> NarrationOut:
        project, estimate, _, provider = self._begin(project_id, approval, "generating_audio", review_override)
        narrations = {item.scene_id: item for item in self.repository.narrations(project_id)}
        arc_revision = NarrationComposerService().revision(project)
        if any(scene.id not in narrations or narrations[scene.id].source_hash != fingerprint([scene.id, arc_revision]) for scene in project.scenes):
            raise HTTPException(status_code=409, detail="Generate current narration for every scene first.")
        if not estimate.estimated_api_calls and not estimate.estimated_runtime_seconds:
            raise HTTPException(status_code=409, detail="All narration audio is already generated.")
        if project.input_manifest.get("source_audio"):
            from services.input_analysis_service import InputAnalysisService
            source = project.input_manifest.get("transcript") or project.input_manifest.get("text")
            if not source or not Path(project.input_manifest["source_audio"]).is_file():
                raise HTTPException(status_code=409,detail="Original narration text/audio is missing. Restore your media backup.")
            InputAnalysisService(self.repository).attach_supplied_narration(project,source,missing_only=True)
            project.status = "audio_ready"
            self.repository.save()
            return self.get(project_id)
        if provider is None:
            raise RuntimeError("A provider is required for speech generation.")
        project.status = "generating_audio"
        self.repository.save()
        try:
            for scene in sorted(project.scenes, key=lambda item: item.scene_number):
                item = narrations[scene.id]
                if item.audio_path and Path(item.audio_path).is_file():
                    continue
                # Reserve per call; completed audio is checkpointed and never billed again on retry.
                self.repository.lock_project(project_id)
                cost = round(len(item.text) / 1000 * float(os.getenv("ESTIMATED_SPEECH_USD_PER_1K_CHARACTERS", "0.015")), 4)
                ProjectService._reserve_estimated_cost(project, cost)
                self.repository.save()
                path = media.STORAGE_DIR / "projects" / str(project_id) / f"narration-{uuid4().hex}.wav"
                try:
                    provider.generate_speech(item.text, path)
                    with wave.open(str(path), "rb") as audio:
                        # Streaming WAV headers can advertise an unknown (oversized) frame count.
                        byte_count = 0
                        while chunk := audio.readframes(65536):
                            byte_count += len(chunk)
                        seconds = byte_count / (
                            audio.getframerate() * audio.getnchannels() * audio.getsampwidth()
                        )
                    if not math.isfinite(seconds) or not 0 < seconds <= 3600:
                        raise AIProviderError("Speech must contain between 0 and 3600 seconds of audio.")
                except (wave.Error, EOFError, OSError) as error:
                    path.unlink(missing_ok=True)
                    raise AIProviderError("The provider returned invalid WAV speech audio.") from error
                except AIProviderError:
                    path.unlink(missing_ok=True)
                    raise
                item.audio_path = str(path)
                item.audio_seconds = seconds
                item.speech_model, item.voice = speech_settings()
                self.repository.add_asset(project_id=project_id, asset_type="narration_audio", file_path=str(path))
                self.repository.save()
            project.status = "audio_ready"
            self.repository.save()
        except Exception:
            logger.exception("Audio generation failed for project %s", project_id)
            self._fail(project_id)
            raise
        return self.get(project_id)

    def _fail(self, project_id: int) -> None:
        self.repository.db.rollback()
        project = ProjectService(self.repository).get(project_id)
        project.status = "narration_failed"
        self.repository.save()
