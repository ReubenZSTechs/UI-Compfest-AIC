# app/api/v1/endpoints/digital_twin_ingestion.py
from fastapi import APIRouter

from app.modules.digital_twin_ingestion import service
from app.modules.digital_twin_ingestion.schemas import (
    DigitalTwin,
    Asset,
    Worker,
    JobDesk,
    CompatibilityEvaluation,
    FactoryFlowRightNow,
)

router = APIRouter()


@router.get("", response_model=DigitalTwin)
def read_full_twin():
    return service.get_full_twin()


@router.get("/assets", response_model=list[Asset])
def read_assets():
    return service.get_assets()


@router.get("/workers", response_model=list[Worker])
def read_workers():
    return service.get_workers()


@router.get("/job-desks", response_model=list[JobDesk])
def read_job_desks():
    return service.get_job_desks()


@router.get("/compatibility-matrix", response_model=list[CompatibilityEvaluation])
def read_compatibility_matrix():
    return service.get_compatibility_matrix()


@router.get("/live-flow", response_model=FactoryFlowRightNow)
def read_live_flow():
    return service.get_live_flow()