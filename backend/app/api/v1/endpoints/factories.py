# app/api/v1/endpoints/factories.py
"""
Endpoint factory-scoped: factory_id sebagai path parameter, bukan query string
opsional. Ini kontrak kanonik untuk Digital Twin & Simulation.

    POST /factories                                 -> Langkah 1: buat factory_id
    GET  /factories                                 -> daftar factory + status pipeline
    GET  /factories/{factory_id}                    -> ringkasan satu factory
    GET  /factories/{factory_id}/digital-twin       -> Digital Twin lengkap
    GET  /factories/{factory_id}/simulation-config  -> konfigurasi tick loop simulasi
    PUT  /factories/{factory_id}/simulation         -> Langkah 3: simpan flowchart manual
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.digital_twin_ingestion.schemas import (
    DigitalTwin,
    FactoryCreateRequest,
    FactorySummary,
)
from app.modules.digital_twin_ingestion.service import DigitalTwinService
from app.modules.simulation import schemas as simulation_schemas
from app.modules.simulation import service as simulation_service
from app.modules.simulation.exceptions import SimulationError

router = APIRouter()


def _simulation_error(error: SimulationError) -> HTTPException:
    code = (
        status.HTTP_404_NOT_FOUND
        if error.stage == "factory_lookup"
        else status.HTTP_422_UNPROCESSABLE_ENTITY
    )
    return HTTPException(status_code=code, detail=error.to_dict())


@router.post(
    "",
    response_model=FactorySummary,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    summary="Langkah 1: Inisialisasi factory & generasi factory_id unik",
)
async def create_factory(
    payload: FactoryCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> FactorySummary:
    service = DigitalTwinService(db)
    try:
        factory = await service.create_factory(payload)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error

    summary = await service.get_summary(factory.factory_id)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Factory berhasil dibuat namun ringkasannya gagal dibaca kembali.",
        )
    return summary


@router.get(
    "",
    response_model=list[FactorySummary],
    response_model_by_alias=True,
    summary="Daftar factory beserta status pipeline digital twin-nya",
)
async def list_factories(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[FactorySummary]:
    return await DigitalTwinService(db).list_factories(limit=limit, offset=offset)


@router.get(
    "/{factory_id}",
    response_model=FactorySummary,
    response_model_by_alias=True,
    summary="Ringkasan satu factory (jumlah entitas & status pipeline)",
)
async def get_factory_summary(
    factory_id: str,
    db: AsyncSession = Depends(get_db),
) -> FactorySummary:
    summary = await DigitalTwinService(db).get_summary(factory_id)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factory '{factory_id}' tidak ditemukan.",
        )
    return summary


@router.get(
    "/{factory_id}/digital-twin",
    response_model=DigitalTwin,
    response_model_by_alias=True,
    summary="Ambil Digital Twin untuk satu factory (factory_id wajib, path param)",
)
async def get_factory_digital_twin(
    factory_id: str,
    db: AsyncSession = Depends(get_db),
) -> DigitalTwin:
    service = DigitalTwinService(db)
    if await service.get_factory(factory_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factory '{factory_id}' tidak ditemukan.",
        )
    return await service.get_full_twin(factory_id)


@router.put(
    "/{factory_id}/simulation",
    response_model=simulation_schemas.SimulationDesignResponse,
    response_model_by_alias=True,
    summary="Langkah 3: Simpan flowchart/simulasi manual milik satu factory",
)
async def save_factory_simulation(
    factory_id: str,
    payload: simulation_schemas.SimulationDesignRequest,
    db: AsyncSession = Depends(get_db),
) -> simulation_schemas.SimulationDesignResponse:
    try:
        return await simulation_service.save_simulation_design(db, factory_id, payload)
    except SimulationError as error:
        raise _simulation_error(error) from error


@router.get(
    "/{factory_id}/simulation-config",
    response_model=simulation_schemas.SimulationConfig,
    summary="Ambil konfigurasi simulasi untuk satu factory (factory_id wajib, path param)",
)
async def get_factory_simulation_config(
    factory_id: str,
    db: AsyncSession = Depends(get_db),
) -> simulation_schemas.SimulationConfig:
    try:
        return await simulation_service.get_simulation_config(
            db=db, factory_id=factory_id
        )
    except SimulationError as error:
        raise _simulation_error(error) from error