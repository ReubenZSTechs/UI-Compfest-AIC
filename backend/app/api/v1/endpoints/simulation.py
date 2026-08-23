"""
Endpoint modul simulation.

Backend stateless: tidak ada tick engine, tidak ada in-memory state, tidak ada
WebSocket. Simulation engine (tick loop, fatigue/stress, mass balance, shift
scheduler) sepenuhnya berjalan di frontend memakai angka dari endpoint ini.

    POST /simulation/{factory_id}   -> simpan flowchart manual (Langkah 3)
    GET  /simulation/{factory_id}   -> seluruh data simulasi + graf flowchart (Langkah 5)
    GET  /simulation/config         -> [deprecated] konfigurasi tick loop via query param
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.simulation import schemas, service
from app.modules.simulation.exceptions import SimulationError

router = APIRouter()


def _simulation_error(error: SimulationError) -> HTTPException:
    code = (
        status.HTTP_404_NOT_FOUND
        if error.stage == "factory_lookup"
        else status.HTTP_422_UNPROCESSABLE_ENTITY
    )
    return HTTPException(status_code=code, detail=error.to_dict())


@router.get(
    "/config",
    response_model=schemas.SimulationConfig,
    summary="[DEPRECATED] Gunakan GET /factories/{factory_id}/simulation-config",
    deprecated=True,
    description=(
        "Dipertahankan untuk kompatibilitas mundur. factory_id di sini OPSIONAL "
        "(query param); endpoint kanonik adalah "
        "GET /factories/{factory_id}/simulation-config."
    ),
)
async def get_simulation_config(
    factory_id: Optional[str] = Query(
        None,
        description=(
            "ID pabrik yang datanya dipakai membangun konfigurasi simulasi. "
            "Kosongkan untuk memakai factory terakhir yang dikonfigurasi."
        ),
    ),
    db: AsyncSession = Depends(get_db),
) -> schemas.SimulationConfig:
    return await service.get_simulation_config(db=db, factory_id=factory_id)


@router.post(
    "/{factory_id}",
    response_model=schemas.SimulationDesignResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_200_OK,
    summary="Langkah 3: Simpan flowchart/simulasi manual dari UI",
)
async def save_simulation_design(
    factory_id: str,
    payload: schemas.SimulationDesignRequest,
    db: AsyncSession = Depends(get_db),
) -> schemas.SimulationDesignResponse:
    try:
        return await service.save_simulation_design(db, factory_id, payload)
    except SimulationError as error:
        raise _simulation_error(error) from error


@router.get(
    "/{factory_id}",
    response_model=schemas.SimulationOverview,
    response_model_by_alias=True,
    summary="Langkah 5: Ambil seluruh data simulasi berdasarkan factory_id",
)
async def get_simulation_overview(
    factory_id: str,
    db: AsyncSession = Depends(get_db),
) -> schemas.SimulationOverview:
    try:
        return await service.get_simulation_overview(db, factory_id)
    except SimulationError as error:
        raise _simulation_error(error) from error