from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.digital_twin_ingestion.schemas import (
    Asset,
    CompatibilityEvaluation,
    DigitalTwin,
    FactoryDigitalTwinResponse,
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
    summary="Mendapatkan Data Digital Twin Lengkap",
    description="Mengambil data Digital Twin lengkap berdasarkan jobId (opsional). Jika jobId kosong, mengambil data terbaru.",
)
async def read_full_twin(
    job_id: Optional[str] = Query(None, description="ID Job Parsing (opsional)"),
    jobId: Optional[str] = Query(None, description="ID Job Parsing (alias jobId)", include_in_schema=False),
    db: AsyncSession = Depends(get_db),
) -> DigitalTwin:
    service = DigitalTwinService(db)
    return await service.get_full_twin(job_id=job_id or jobId)


@router.get(
    "/assets",
    response_model=list[Asset],
    status_code=status.HTTP_200_OK,
    summary="Mendapatkan daftar seluruh Asset/Mesin",
)
async def read_assets(
    job_id: Optional[str] = Query(None, description="ID Job Parsing (opsional)"),
    jobId: Optional[str] = Query(None, description="ID Job Parsing (alias jobId)", include_in_schema=False),
    db: AsyncSession = Depends(get_db),
) -> list[Asset]:
    service = DigitalTwinService(db)
    return await service.get_assets(job_id=job_id or jobId)


@router.get(
    "/workers",
    response_model=list[Worker],
    status_code=status.HTTP_200_OK,
    summary="Mendapatkan daftar seluruh Pekerja",
)
async def read_workers(
    job_id: Optional[str] = Query(None, description="ID Job Parsing (opsional)"),
    jobId: Optional[str] = Query(None, description="ID Job Parsing (alias jobId)", include_in_schema=False),
    db: AsyncSession = Depends(get_db),
) -> list[Worker]:
    service = DigitalTwinService(db)
    return await service.get_workers(job_id=job_id or jobId)


@router.get(
    "/job-desks",
    response_model=list[JobDesk],
    status_code=status.HTTP_200_OK,
    summary="Mendapatkan daftar seluruh Job Desk",
)
async def read_job_desks(
    job_id: Optional[str] = Query(None, description="ID Job Parsing (opsional)"),
    jobId: Optional[str] = Query(None, description="ID Job Parsing (alias jobId)", include_in_schema=False),
    db: AsyncSession = Depends(get_db),
) -> list[JobDesk]:
    service = DigitalTwinService(db)
    return await service.get_job_desks(job_id=job_id or jobId)


@router.get(
    "/compatibility-matrix",
    response_model=list[CompatibilityEvaluation],
    status_code=status.HTTP_200_OK,
    summary="Mendapatkan Matriks Evaluasi Kompatibilitas",
)
async def read_compatibility_matrix(
    job_id: Optional[str] = Query(None, description="ID Job Parsing (opsional)"),
    jobId: Optional[str] = Query(None, description="ID Job Parsing (alias jobId)", include_in_schema=False),
    db: AsyncSession = Depends(get_db),
) -> list[CompatibilityEvaluation]:
    service = DigitalTwinService(db)
    return await service.get_compatibility_matrix(job_id=job_id or jobId)


@router.get(
    "/live-flow",
    response_model=Optional[FactoryFlowRightNow],
    status_code=status.HTTP_200_OK,
    summary="Mendapatkan snapshot arus produksi real-time",
)
async def read_live_flow(
    job_id: Optional[str] = Query(None, description="ID Job Parsing (opsional)"),
    jobId: Optional[str] = Query(None, description="ID Job Parsing (alias jobId)", include_in_schema=False),
    db: AsyncSession = Depends(get_db),
) -> Optional[FactoryFlowRightNow]:
    service = DigitalTwinService(db)
    return await service.get_live_flow(job_id=job_id or jobId)


# CATATAN: route dinamis di bawah WAJIB dideklarasikan paling akhir supaya tidak
# menelan path statis di atas ("/assets", "/workers", "/job-desks", dst.).

@router.get(
    "/{factory_id}",
    response_model=FactoryDigitalTwinResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_200_OK,
    summary="Langkah 5: Ambil Digital Twin lengkap berdasarkan factory_id",
)
async def read_twin_by_factory(
    factory_id: str = Path(..., description="ID Pabrik hasil inisialisasi (POST /factories)"),
    db: AsyncSession = Depends(get_db),
) -> FactoryDigitalTwinResponse:
    service = DigitalTwinService(db)
    response = await service.get_twin_response(factory_id)
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factory '{factory_id}' tidak ditemukan.",
        )
    return response


@router.get(
    "/{factory_id}/compatibility-matrix",
    response_model=list[CompatibilityEvaluation],
    response_model_by_alias=True,
    status_code=status.HTTP_200_OK,
    summary="Ambil Matriks Kompatibilitas satu factory",
)
async def read_matrix_by_factory(
    factory_id: str = Path(..., description="ID Pabrik hasil inisialisasi (POST /factories)"),
    db: AsyncSession = Depends(get_db),
) -> list[CompatibilityEvaluation]:
    service = DigitalTwinService(db)
    if await service.get_factory(factory_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factory '{factory_id}' tidak ditemukan.",
        )
    return await service.get_compatibility_matrix(factory_id)