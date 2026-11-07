import base64
import binascii
import io
import math
import os
from pathlib import Path
import re
from uuid import uuid4
import wave

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

from models.models import Character, Narration, Project, Scene
from repositories.production_repository import ProductionRepository
from schemas.ai_schemas import CharacterBible, CharacterBibleData, CharacterSeed, StoryBibleData, ThreeActStructure
from schemas.inputs import InputBundle, InputClassification, InputState, SuppliedFile, SuppliedScene, TranscriptionRequest
from schemas.production import ProductionEstimate
from services.ai.configuration import create_ai_provider, get_ai_configuration
from services.ai.estimation_service import AIEstimationService, GenerationEstimate
from services.ai.providers.base import AIProvider
from services.image_service import public_asset_url
from services.project_service import ProjectService
from services.scene_motion_planner import SceneMotionPlanner
from services.timeline_service import fingerprint
from services.video_composer_service import VideoComposerService
import services.image_service as media


class InputAnalysisService:
    def __init__(self, repository: ProductionRepository):
        self.repository = repository

    @staticmethod
    def classify(bundle: InputBundle) -> InputClassification:
        from services.document_input_service import DocumentInputService
        bundle = DocumentInputService.expand(bundle)
        kinds = []
        if bundle.text.strip():
            kind = bundle.text_kind
            if kind == "auto":
                if re.search(r"(?im)^\s*(scene\s+\d+|INT\.|EXT\.)", bundle.text):
                    kind = "scene_descriptions"
                elif re.search(r"(?im)^\s*(narrator:|voiceover:|narration:)", bundle.text):
                    kind = "narration_script"
                elif re.search(r"(?im)^\s*(character:|name:)", bundle.text):
                    kind = "character_definitions"
                else:
                    kind = "text_story"
            kinds.append(kind)
        if bundle.scenes:
            kinds.append("scene_descriptions")
        if bundle.characters:
            kinds.append("character_definitions")
        if bundle.images:
            kinds.append("image_collection")
        if bundle.audio:
            kinds.append("audio_file")
        kinds = list(dict.fromkeys(kinds))
        if not kinds:
            raise HTTPException(status_code=422, detail="Supply at least one story, scene, script, character, image or audio input.")
        workflow = ["Import and review supplied content"]
        if bundle.audio:
            workflow.append("Approve timestamp-transcription estimate and align supplied audio")
        if "text_story" not in kinds:
            workflow.append("Derive missing story structure from all supplied content")
        if "character_definitions" not in kinds:
            workflow.append("Generate missing character definitions")
        if not (bundle.scenes or bundle.images or "scene_descriptions" in kinds):
            workflow.append("Segment preserved narration at sentence boundaries and align original audio timestamps" if bundle.audio or "narration_script" in kinds else "Generate missing scene plan")
        workflow.extend(["Review story and approve character portraits", "Generate missing scene images and review scenes"])
        if "narration_script" not in kinds and not bundle.audio:
            workflow.append("Compose connected narration after scene review")
        if not bundle.audio:
            workflow.append("Approve speech estimate and generate missing audio")
        workflow.append("Review timeline and readiness, approve render estimates, render and download")
        return InputClassification(
            kinds=kinds + (["mixed_inputs"] if len(kinds) > 1 else []),
            workflow=workflow,
            preserved=kinds,
            limitations=[
                "Automatic text classification is heuristic; select a type to correct it.",
                "Images need descriptions; this import does not claim to recognize image contents.",
                "Audio is normalized locally; transcription is a separately approved paid call.",
                "Audio uses approved word-timestamp transcription for scene boundaries; review timing before rendering.",
            ],
            needs_transcription=bundle.audio is not None,
        )

    @staticmethod
    def decode(file: SuppliedFile) -> bytes:
        try:
            data = base64.b64decode(file.content_base64, validate=True)
        except (binascii.Error, ValueError) as error:
            raise HTTPException(status_code=422, detail="Invalid base64 upload.") from error
        if not data or len(data) > 20_000_000:
            raise HTTPException(status_code=422, detail="Each upload must be 1 byte to 20 MB.")
        return data

    def import_bundle(self, project_id: int, bundle: InputBundle) -> InputState:
        from services.document_input_service import DocumentInputService
        original_documents = bundle.documents
        bundle = DocumentInputService.expand(bundle).model_copy(update={"documents": []})
        classification = self.classify(bundle)
        if sum(len(item.content_base64) for item in [*bundle.images, *original_documents]) + (len(bundle.audio.content_base64) if bundle.audio else 0) > 54_000_000:
            raise HTTPException(status_code=422,detail="Combined uploads exceed 40 MB.")
        self.repository.begin_write()
        self.repository.lock_project(project_id)
        self.repository.require_no_active_job(project_id)
        project = ProjectService(self.repository).get(project_id)
        if project.status=="planning":
            raise HTTPException(status_code=409,detail="Wait for planning to finish before importing inputs.")
        if project.scenes or project.characters or project.input_manifest:
            raise HTTPException(status_code=409, detail="Import is only available before planning. Create a new project to replace supplied content.")
        if bundle.images and any(not item.description.strip() for item in bundle.images):
            raise HTTPException(status_code=422, detail="Describe each uploaded image so its scene plan can be grounded in supplied information.")
        if bundle.images and bundle.scenes and len(bundle.images) != len(bundle.scenes):
            raise HTTPException(status_code=422, detail="Provide one image for each supplied scene, in scene order.")
        directory = media.STORAGE_DIR / "projects" / str(project_id)
        directory.mkdir(parents=True, exist_ok=True)
        written = []
        total_bytes = 0
        try:
            document_sources = []
            for item in original_documents:
                data = self.decode(item)
                total_bytes += len(data)
                original = directory / f"source-{uuid4().hex}{Path(item.name).suffix.lower()}"
                original.write_bytes(data)
                written.append(original)
                document_sources.append(public_asset_url(original))
                self.repository.add_asset(project_id=project_id, asset_type="supplied_document", file_path=str(original))
            scenes = list(bundle.scenes)
            if not scenes and "scene_descriptions" in classification.kinds:
                paragraphs = [part.strip() for part in re.split(r"(?im)(?=^[ \t]*(?:scene\s+\d+|INT\.|EXT\.))|\n\s*\n", bundle.text) if part.strip()]
                if len(paragraphs) > 12:
                    raise HTTPException(status_code=422, detail="At most 12 supplied scenes are supported.")
                if any(len(part)>4000 for part in paragraphs):
                    raise HTTPException(status_code=422,detail="Each scene description must be at most 4000 characters.")
                scenes = [SuppliedScene(title=part.splitlines()[0][:160], description=part) for part in paragraphs]
            if bundle.images and not scenes:
                scenes = [SuppliedScene(title=f"Image scene {index}", description=item.description) for index, item in enumerate(bundle.images, 1)]
            if bundle.images and len(bundle.images)!=len(scenes):
                raise HTTPException(status_code=422,detail="Provide one image for each supplied scene, in scene order.")
            for index, item in enumerate(scenes, 1):
                scene = Scene(project_id=project_id, scene_number=index, title=item.title, description=item.description,
                              visual_description=item.description, image_prompt=item.description, estimated_duration=item.duration_seconds)
                project.scenes.append(scene)
                self.repository.db.flush()
                if bundle.images:
                    data = self.decode(bundle.images[index-1])
                    total_bytes += len(data)
                    if total_bytes>40_000_000:
                        raise HTTPException(status_code=422,detail="Combined uploads exceed 40 MB.")
                    try:
                        with Image.open(io.BytesIO(data)) as image:
                            if image.width * image.height > 25_000_000:
                                raise HTTPException(status_code=422, detail="Uploaded image exceeds 25 megapixels.")
                            path = directory / f"import-{uuid4().hex}.png"
                            written.append(path)
                            image.convert("RGB").save(path)
                    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
                        raise HTTPException(status_code=422, detail="Upload a valid PNG/JPEG/WebP image.") from error
                    scene.image_path = public_asset_url(path)
                    scene.status = "generated"
                    self.repository.add_asset(project_id=project_id, asset_type="supplied_image", file_path=str(path))
            for item in bundle.characters:
                from services.story_service import StoryService
                project.characters.append(StoryService._character_model(item))
            if not bundle.characters and "character_definitions" in classification.kinds:
                blocks = [part.strip() for part in re.split(r"(?im)(?=^(?:character|name):)", bundle.text) if part.strip()]
                if len(blocks)>12:
                    raise HTTPException(status_code=422,detail="At most 12 supplied character definitions are supported.")
                for block in blocks:
                    name = re.sub(r"(?i)^(character|name):\s*", "", block.splitlines()[0]).strip()
                    if not 1<=len(name)<=120:
                        raise HTTPException(status_code=422,detail="Character definitions need a name of 1-120 characters on their first line.")
                    project.characters.append(Character(
                        name=name, role="Supplied character", description=block,
                        appearance=block, portrait_prompt=block,
                    ))
            text = bundle.text
            source_audio = None
            raw = None
            audio_seconds = None
            if bundle.audio:
                data = self.decode(bundle.audio)
                total_bytes += len(data)
                if total_bytes>40_000_000:
                    raise HTTPException(status_code=422,detail="Combined uploads exceed 40 MB.")
                suffix = Path(bundle.audio.name).suffix.lower()
                if suffix not in {".wav", ".mp3", ".m4a", ".flac", ".ogg"}:
                    raise HTTPException(status_code=422, detail="Supported audio: WAV, MP3, M4A, FLAC, OGG.")
                raw = directory / f"source-{uuid4().hex}{suffix}"
                written.append(raw)
                raw.write_bytes(data)
                source_audio = directory / f"source-{uuid4().hex}.wav"
                written.append(source_audio)
                try:
                    VideoComposerService()._run([
                        "-y", "-protocol_whitelist", "file,pipe", "-i", str(raw), "-vn",
                        "-t", "601", "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(source_audio),
                    ])
                    with wave.open(str(source_audio), "rb") as audio:
                        audio_seconds = audio.getnframes() / audio.getframerate()
                except (RuntimeError, wave.Error) as error:
                    raise HTTPException(status_code=422, detail="Could not decode uploaded audio.") from error
                if not 0 < audio_seconds <= 600:
                    raise HTTPException(status_code=422, detail="Uploaded audio must be between 0 and 10 minutes.")
                self.repository.add_asset(project_id=project_id,asset_type="supplied_original_audio",file_path=str(raw))
                self.repository.add_asset(project_id=project_id,asset_type="supplied_audio_source",file_path=str(source_audio))
            if "text_story" in classification.kinds:
                project.title = bundle.title
                project.story_summary = text
            manifest = {
                "classification": classification.model_dump(), "text": text, "title": bundle.title,
                "text_kind": next((kind for kind in classification.kinds if kind in {"text_story","narration_script","scene_descriptions","character_definitions"}), ""),
                "source_audio": str(source_audio) if source_audio else None, "audio_seconds": audio_seconds,
                "original_audio":str(raw) if raw else None,
                "supplied_scenes": bool(scenes), "supplied_characters": bool(bundle.characters),
                "preserve_narration": "narration_script" in classification.kinds or bool(source_audio),
                "transcript": text if source_audio and "narration_script" in classification.kinds else "",
                "document_sources": document_sources,
            }
            project.input_manifest = manifest
            project.status = "inputs_imported"
            self.repository.save()
        except Exception:
            self.repository.db.rollback()
            for path in written:
                path.unlink(missing_ok=True)
            raise
        return InputState(classification=classification, manifest=self.public_manifest(project))

    @staticmethod
    def public_manifest(project: Project) -> dict:
        return {key: value for key, value in project.input_manifest.items() if key not in {"source_audio","original_audio"}}

    def planning_estimate(self, project: Project, configuration) -> GenerationEstimate:
        estimator = AIEstimationService()
        operations = []
        if not project.story_summary:
            operations.append(estimator.estimate("story", configuration))
        if not project.characters:
            operations.append(estimator.estimate("characters", configuration, character_count=3))
        if not project.scenes and not project.input_manifest.get("preserve_narration"):
            operations.append(estimator.estimate("scenes", configuration, character_count=len(project.characters) or 3, scene_count=estimator.scene_count_for(project.target_minutes)))
        return GenerationEstimate(
            operation="planning", estimated_cost=round(sum(item.estimated_cost for item in operations),4),
            estimated_minutes=sum(item.estimated_minutes for item in operations),
            estimated_model_usage=f"{len(operations)} missing-asset text calls using {configuration.model}; supplied content is preserved",
            estimated_api_calls=len(operations), notes="Missing assets only. Planning estimates are not provider quotes.",
        )

    def generate_missing(self, project: Project, provider: AIProvider | None) -> None:
        from services.story_service import StoryService
        manifest = project.input_manifest
        if manifest.get("source_audio") and not manifest.get("transcript_words"):
            raise HTTPException(status_code=409, detail="Review the transcription estimate and transcribe supplied audio first.")
        source = manifest.get("transcript") or manifest.get("text") or "\n".join(scene.description for scene in project.scenes) or project.prompt
        if not project.story_summary:
            if provider is None:
                raise RuntimeError("A provider is required for missing story structure.")
            context = "Derive missing story structure from these supplied inputs without contradicting them:\n" + source
            if project.scenes:
                context += "\nPreserve these supplied scene events in order:\n" + "\n".join(scene.description for scene in sorted(project.scenes,key=lambda item:item.scene_number))
            if project.characters:
                context += "\nReuse these character definitions:\n" + str([{"name":item.name,"appearance":item.appearance,"role":item.role} for item in project.characters])
            story = provider.generate_story(context, project.target_minutes)
            project.title, project.story_summary = story.title, story.summary
            project.genre, project.target_audience = story.genre, story.target_audience
            project.three_act_structure = story.three_act_structure.model_dump()
        else:
            story = StoryBibleData(
                title=project.title, summary=project.story_summary, genre=project.genre,
                target_audience=project.target_audience, three_act_structure=ThreeActStructure(
                    **{key:project.three_act_structure.get(key, "Review supplied story structure.") for key in ("act_one","act_two","act_three")}
                ), main_characters=[CharacterSeed(name=item.name,role=item.role or "Character",premise=item.appearance or item.description) for item in project.characters],
            )
        if not project.characters:
            if provider is None:
                raise RuntimeError("A provider is required for missing character definitions.")
            characters = provider.generate_character_bible(story)
            if not characters.characters:
                raise HTTPException(status_code=502, detail="Provider returned no characters from the supplied story.")
            project.characters.extend(StoryService._character_model(item) for item in characters.characters)
        characters = CharacterBible(characters=[
            CharacterBibleData(name=item.name, role=item.role, personality=item.personality,appearance=item.appearance,
             motivations=item.motivations,relationships=item.relationships,portrait_prompt=item.portrait_prompt)
            for item in project.characters
        ])
        if not project.scenes:
            if manifest.get("preserve_narration") and not any(scene.narration for scene in project.scenes):
                from services.story_segmentation_service import StorySegmentationService
                parts = StorySegmentationService.segments(source)
                project.input_manifest = {**manifest, "narration_parts": parts}
                for index, part in enumerate(parts, 1):
                    project.scenes.append(Scene(
                        title=f"{project.title[:140]} / {index}", description=part[:4000],
                        visual_description=f"Depict this sequential event consistently: {part[:3000]}",
                        image_prompt=f"{project.story_summary[:1000]}\nCurrent event: {part[:3000]}",
                        estimated_duration=max(1, math.ceil(len(part.split()) / 2.5)),
                        scene_number=index, beat_number=(index-1)//2+1,
                    ))
            else:
                if provider is None:
                    raise RuntimeError("A provider is required for a missing scene plan.")
                from services.narrative_analysis_service import NarrativeAnalysisService
                narrative = provider.generate_narrative_plan(story, characters, project.target_minutes)
                plan = (NarrativeAnalysisService.flatten(narrative) if narrative else
                        provider.generate_scene_plan(story, characters, project.target_minutes))
                if narrative:
                    NarrativeAnalysisService.store(project, narrative)
                if not 1<=len(plan.scenes)<=12:
                    raise HTTPException(status_code=502,detail="Provider must return 1-12 scenes for imported inputs.")
                project.scenes.extend(StoryService._scene_model(item,index) for index,item in enumerate(plan.scenes,1))
        self.repository.db.flush()
        for scene in project.scenes:
            scene.motion_plan = SceneMotionPlanner().plan(project, scene).model_dump()
        project.status = "analysis_complete"
        if manifest.get("preserve_narration"):
            self.attach_supplied_narration(project, source)

    def attach_supplied_narration(self, project: Project, text: str, *, missing_only: bool = False) -> None:
        from services.narration_composer_service import NarrationComposerService
        revision = NarrationComposerService().revision(project)
        scenes = sorted(project.scenes,key=lambda item:item.scene_number)
        words = text.split()
        parts = project.input_manifest.get("narration_parts", [])
        timed_words = project.input_manifest.get("transcript_words", [])
        if project.input_manifest.get("source_audio") and len(scenes) > 1 and not timed_words:
            raise HTTPException(status_code=409, detail="Approve timestamp transcription before splitting original audio into scenes.")
        if parts and len(parts) != len(scenes):
            raise HTTPException(status_code=409, detail="Preserved narration segmentation no longer matches the scene plan.")
        boundaries = [0]
        for index in range(len(scenes)):
            boundaries.append(boundaries[-1] + len(parts[index].split()) if parts else len(words)*(index+1)//len(scenes))
        for index, scene in enumerate(scenes):
            # Keep original full text for a single scene; otherwise preserve every supplied word in order.
            part = text if len(scenes)==1 else (parts[index] if parts else " ".join(words[boundaries[index]:boundaries[index+1]]))
            if not part.strip():
                raise HTTPException(status_code=422, detail="Supplied script is too short for the scene count.")
            narration = scene.narration or Narration(project_id=project.id, scene_id=scene.id)
            if missing_only and narration.source_hash==fingerprint([scene.id,revision]) and narration.audio_path and Path(narration.audio_path).is_file():
                continue
            narration.audio_path, narration.audio_seconds = None, None
            narration.text = part
            narration.transition_text = ""
            narration.source_hash = fingerprint([scene.id,revision])
            narration.recommended_seconds = len(part.split()) / 2.5
            narration.provider, narration.model = "user", "supplied-script"
            source_path = project.input_manifest.get("source_audio")
            if source_path:
                start = 0 if index == 0 else timed_words[boundaries[index]]["start"]
                end = (project.input_manifest["audio_seconds"] if index == len(scenes)-1
                       else timed_words[boundaries[index+1]]["start"])
                seconds = end - start
                if seconds <= 0:
                    raise HTTPException(status_code=422, detail="Audio timestamp boundaries must advance for every scene.")
                output = Path(source_path).with_name(f"imported-audio-{scene.id}-{uuid4().hex}.wav")
                VideoComposerService()._run([
                    "-y", "-ss", str(start), "-i", source_path, "-t", str(seconds),
                    "-c:a", "pcm_s16le", str(output),
                ])
                narration.audio_path, narration.audio_seconds = str(output), seconds
                scene.estimated_duration = max(scene.estimated_duration, math.ceil(seconds+0.25))
                self.repository.add_asset(project_id=project.id,asset_type="supplied_audio",file_path=str(output))
            scene.narration = narration

    def transcription_estimate(self, project: Project) -> ProductionEstimate:
        manifest = project.input_manifest
        seconds = manifest.get("audio_seconds") or 0
        rate = float(os.getenv("ESTIMATED_TRANSCRIPTION_USD_PER_MINUTE", "0.006"))
        cost = round(seconds/60*rate,4)
        return ProductionEstimate(
            estimate_id=fingerprint(["transcribe",manifest,cost,os.getenv("OPENAI_TRANSCRIPTION_MODEL","whisper-1")]),
            estimated_cost=cost, estimated_runtime_seconds=max(5,seconds/3),
            estimated_storage_mb=seconds*0.048, estimated_audio_seconds=seconds,
            estimated_video_seconds=seconds,estimated_api_calls=1,
            model_usage=os.getenv("OPENAI_TRANSCRIPTION_MODEL","whisper-1"),
        )

    def transcribe(self, project_id: int, payload: TranscriptionRequest) -> InputState:
        self.repository.begin_write()
        self.repository.lock_project(project_id)
        self.repository.require_no_active_job(project_id)
        project = ProjectService(self.repository).get(project_id)
        if not project.input_manifest.get("source_audio"):
            raise HTTPException(status_code=409, detail="Import an audio file first.")
        if not Path(project.input_manifest["source_audio"]).is_file():
            raise HTTPException(status_code=409,detail="Uploaded audio file is missing. Restore the project media backup before transcribing.")
        if project.input_manifest.get("transcript_words"):
            raise HTTPException(status_code=409, detail="A transcript is already supplied; no paid transcription is needed.")
        estimate = self.transcription_estimate(project)
        if payload.estimate_id != estimate.estimate_id:
            raise HTTPException(status_code=409,detail="Transcription estimate changed. Review it again.")
        if estimate.estimated_runtime_seconds > project.max_wait_minutes*60:
            raise HTTPException(status_code=422,detail="Transcription exceeds the project wait limit.")
        provider = create_ai_provider(get_ai_configuration(self.repository.db))
        ProjectService._reserve_estimated_cost(project,estimate.estimated_cost)
        project.status = "transcribing"
        self.repository.save()
        try:
            transcript = provider.transcribe_audio_timed(Path(project.input_manifest["source_audio"]))
            text = transcript.text
            if not text.strip() or len(text)>6000:
                raise HTTPException(status_code=502,detail="Transcript must contain 1-6000 characters.")
            supplied = project.input_manifest.get("transcript")
            def normalized(value):
                return [re.sub(r"\W", "", word).casefold() for word in value.split()]
            if supplied and normalized(supplied) != normalized(text):
                raise HTTPException(status_code=409, detail="Supplied script differs from audio transcript. Original script is preserved; review alignment in a new import.")
            reference = supplied or text
            timed_words = [word.model_dump() for word in transcript.words]
            if normalized(reference) != normalized(" ".join(word["word"] for word in timed_words)):
                raise HTTPException(status_code=502, detail="Transcription words do not align with the preserved script.")
            previous = 0
            for word in timed_words:
                if word["start"] < previous or word["end"] < word["start"] or word["end"] > project.input_manifest["audio_seconds"] + 0.1:
                    raise HTTPException(status_code=502, detail="Provider returned invalid or non-monotonic audio timestamps.")
                previous = word["start"]
            project.input_manifest = {**project.input_manifest,"transcript":reference, "transcript_words":timed_words}
            project.status = "inputs_imported"
            self.repository.save()
        except Exception:
            self.repository.db.rollback()
            project = ProjectService(self.repository).get(project_id)
            project.status = "transcription_failed"
            self.repository.save()
            raise
        return InputState(classification=InputClassification.model_validate(project.input_manifest["classification"]),manifest=self.public_manifest(project))
