# app/modules/digital_twin_ingestion/service.py
from app.modules.digital_twin_ingestion.constants import DIGITAL_TWIN_DATA
from app.modules.digital_twin_ingestion.schemas import (
    DigitalTwin,
    Asset,
    Worker,
    JobDesk,
    CompatibilityEvaluation,
    FactoryFlowRightNow,
)


def _load_twin() -> DigitalTwin:
    return DigitalTwin.model_validate(DIGITAL_TWIN_DATA)


def get_full_twin() -> DigitalTwin:
    return _load_twin()


def get_assets() -> list[Asset]:
    return _load_twin().assets


def get_workers() -> list[Worker]:
    return _load_twin().workers


def get_job_desks() -> list[JobDesk]:
    return _load_twin().job_desks


def get_compatibility_matrix() -> list[CompatibilityEvaluation]:
    return _load_twin().llm_compatibility_and_evaluations


def get_live_flow() -> FactoryFlowRightNow:
    return _load_twin().factory_flow_rightnow