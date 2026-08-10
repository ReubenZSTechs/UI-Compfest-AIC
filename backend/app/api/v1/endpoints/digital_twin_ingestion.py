# backend/app/api/v1/endpoints/digital_twin_ingestion.py
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.digital_twin_ingestion.schemas import (
    Asset,
    CompatibilityEvaluation,
    DigitalTwin,
    FactoryFlowRightNow,
    JobDesk,
    Worker,
)
from app.modules.digital_twin_ingestion.service import DigitalTwinService

router = APIRouter()


@router.get(
    "",
    response_model=DigitalTwin,
    status_code=status.HTTP_200_OK,
    summary="Mendapatkan data lengkap Digital Twin",
)
async def read_full_twin(
    factory_id: Optional[str] = Query(None, description="ID Pabrik (opsional)"),
    db: AsyncSession = Depends(get_db),
) -> DigitalTwin:
    service = DigitalTwinService(db)
    return await service.get_full_twin(factory_id=factory_id)


@router.get(
    "/assets",
    response_model=list[Asset],
    status_code=status.HTTP_200_OK,
    summary="Mendapatkan daftar seluruh Asset/Mesin",
)
async def read_assets(
    factory_id: Optional[str] = Query(None, description="ID Pabrik (opsional)"),
    db: AsyncSession = Depends(get_db),
) -> list[Asset]:
    service = DigitalTwinService(db)
    return await service.get_assets(factory_id=factory_id)


@router.get(
    "/workers",
    response_model=list[Worker],
    status_code=status.HTTP_200_OK,
    summary="Mendapatkan daftar seluruh Pekerja",
)
async def read_workers(
    factory_id: Optional[str] = Query(None, description="ID Pabrik (opsional)"),
    db: AsyncSession = Depends(get_db),
) -> list[Worker]:
    service = DigitalTwinService(db)
    return await service.get_workers(factory_id=factory_id)


@router.get(
    "/job-desks",
    response_model=list[JobDesk],
    status_code=status.HTTP_200_OK,
    summary="Mendapatkan daftar seluruh Job Desk",
)
async def read_job_desks(
    factory_id: Optional[str] = Query(None, description="ID Pabrik (opsional)"),
    db: AsyncSession = Depends(get_db),
) -> list[JobDesk]:
    service = DigitalTwinService(db)
    return await service.get_job_desks(factory_id=factory_id)


@router.get(
    "/compatibility-matrix",
    response_model=list[CompatibilityEvaluation],
    status_code=status.HTTP_200_OK,
    summary="Mendapatkan Matriks Evaluasi Kompatibilitas",
)
async def read_compatibility_matrix(
    factory_id: Optional[str] = Query(None, description="ID Pabrik (opsional)"),
    db: AsyncSession = Depends(get_db),
) -> list[CompatibilityEvaluation]:
    service = DigitalTwinService(db)
    return await service.get_compatibility_matrix(factory_id=factory_id)


@router.get(
    "/live-flow",
    response_model=Optional[FactoryFlowRightNow],
    status_code=status.HTTP_200_OK,
    summary="Mendapatkan snapshot arus produksi real-time",
)
async def read_live_flow(
    factory_id: Optional[str] = Query(None, description="ID Pabrik (opsional)"),
    db: AsyncSession = Depends(get_db),
) -> Optional[FactoryFlowRightNow]:
    service = DigitalTwinService(db)
    return await service.get_live_flow(factory_id=factory_id)