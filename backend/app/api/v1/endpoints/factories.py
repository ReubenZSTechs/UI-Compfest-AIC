# app/api/v1/endpoints/factories.py
"""
Endpoint "factory-scoped" -- factory_id sebagai path parameter, bukan query
string opsional. Ini kontrak KANONIK baru untuk Digital Twin & Simulation,
menggantikan pola lama `GET /digital-twin?factory_id=` dan
`GET /simulation/config?factory_id=` yang membuat factory_id gampang
terlewat (query param opsional -> gampang lupa dikirim frontend, seperti
yang sempat terjadi di `features/simulation/api/simulationApi.ts`).

Desain REST: factory adalah parent resource, digital-twin & simulation-config
adalah sub-resource-nya:

    GET /factories/{factory_id}/digital-twin
    GET /factories/{factory_id}/simulation-config

Keduanya TIDAK mengimplementasikan logic baru -- murni delegasi ke service
yang sudah ada (`DigitalTwinService`, `simulation.service`), supaya tidak ada
implementasi kedua yang bisa divergen dari endpoint lama.

Endpoint lama (`GET /digital-twin`, `GET /simulation/config` dengan query
param opsional) TETAP ADA untuk sementara (ditandai `deprecated=True`) supaya
konsumen lain yang belum dimigrasikan tidak langsung patah -- lihat catatan
migrasi di README/docs.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.digital_twin_ingestion.schemas import DigitalTwin
from app.modules.digital_twin_ingestion.service import DigitalTwinService
from app.modules.simulation import schemas as simulation_schemas
from app.modules.simulation import service as simulation_service

router = APIRouter()


@router.get(
    "/{factory_id}/digital-twin",
    response_model=DigitalTwin,
    status_code=status.HTTP_200_OK,
    summary="Ambil Digital Twin untuk satu factory (factory_id wajib, path param)",
)
async def get_factory_digital_twin(
    factory_id: str,
    db: AsyncSession = Depends(get_db),
) -> DigitalTwin:
    twin = await DigitalTwinService(db).get_full_twin(factory_id)
    if not twin.process_stages and not twin.factory_info.workflow_sequence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Digital twin untuk factory_id '{factory_id}' tidak ditemukan / belum di-parse.",
        )
    return twin


@router.get(
    "/{factory_id}/simulation-config",
    response_model=simulation_schemas.SimulationConfig,
    status_code=status.HTTP_200_OK,
    summary="Ambil konfigurasi simulasi untuk satu factory (factory_id wajib, path param)",
)
async def get_factory_simulation_config(
    factory_id: str,
    db: AsyncSession = Depends(get_db),
) -> simulation_schemas.SimulationConfig:
    return await simulation_service.get_simulation_config(db=db, factory_id=factory_id)
