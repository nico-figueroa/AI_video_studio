from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from repositories.production_repository import ProductionRepository
from schemas.inputs import InputBundle, InputClassification, InputState, TranscriptionRequest
from schemas.production import ProductionEstimate
from services.input_analysis_service import InputAnalysisService
from services.project_service import ProjectService

router = APIRouter(prefix="/api/v1")


@router.post("/inputs/classify", response_model=InputClassification)
def classify(payload: InputBundle) -> InputClassification:
    return InputAnalysisService.classify(payload)


@router.post("/projects/{project_id}/inputs", response_model=InputState)
def import_inputs(project_id: int, payload: InputBundle, db: Session = Depends(get_db)) -> InputState:
    return InputAnalysisService(ProductionRepository(db)).import_bundle(project_id, payload)


@router.get("/projects/{project_id}/inputs", response_model=InputState | None)
def get_inputs(project_id: int, db: Session = Depends(get_db)) -> InputState | None:
    project = ProjectService(ProductionRepository(db)).get(project_id)
    if not project.input_manifest:
        return None
    return InputState(
        classification=InputClassification.model_validate(project.input_manifest["classification"]),
        manifest=InputAnalysisService.public_manifest(project),
    )


@router.get("/projects/{project_id}/inputs/transcription-estimate", response_model=ProductionEstimate)
def transcription_estimate(project_id: int, db: Session = Depends(get_db)) -> ProductionEstimate:
    repository = ProductionRepository(db)
    project = ProjectService(repository).get(project_id)
    if not project.input_manifest.get("source_audio"):
        raise HTTPException(status_code=409, detail="No uploaded audio to transcribe.")
    return InputAnalysisService(repository).transcription_estimate(project)


@router.post("/projects/{project_id}/inputs/transcribe", response_model=InputState)
def transcribe(project_id: int, payload: TranscriptionRequest, db: Session = Depends(get_db)) -> InputState:
    return InputAnalysisService(ProductionRepository(db)).transcribe(project_id,payload)
