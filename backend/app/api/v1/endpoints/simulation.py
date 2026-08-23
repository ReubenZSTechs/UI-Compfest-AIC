"""
Endpoint untuk simulation module.

Backend di sini stateless -- tidak ada tick engine, tidak ada in-memory state,
tidak ada WebSocket. Simulation engine (tick loop, worker fatigue/stress, mass
balance, shift scheduler) sepenuhnya jalan di frontend.

- GET /simulation/config -> satu-satunya endpoint. Mengirim recipe table,
  kapasitas, worker seed, dan jadwal shift yang dipakai frontend untuk
  menginisialisasi state machine lokalnya (lihat `simulationApi.ts` ->
  `loadConfig()`).

Frontend memanggil endpoint ini SEKALI di awal load (dan cache promise-nya di
module scope) per factory yang aktif.

REVISI (fix data-sync Simulation API <-> Digital Twin API):
Endpoint ini sekarang menerima `db` dan `factory_id` opsional, dan
meneruskannya ke `service.get_simulation_config()` yang membaca dari Digital
Twin DB -- sumber data yang sama persis dengan `GET /digital-twin`. Kalau
belum ada factory yang di-parse, response otomatis fallback ke seed statis
lama (lihat `service._static_fallback_config()`), jadi tidak ada breaking
change untuk konsumen existing yang belum mengirim `factory_id`.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.simulation import schemas, service

router = APIRouter()


@router.get(
    "/config",
    response_model=schemas.SimulationConfig,
    summary="[DEPRECATED] Gunakan GET /factories/{factory_id}/simulation-config",
    deprecated=True,
    description=(
        "Dipertahankan sementara untuk kompatibilitas mundur. factory_id di "
        "sini OPSIONAL (query param) -- endpoint kanonik baru adalah "
        "GET /factories/{factory_id}/simulation-config (path param, wajib)."
    ),
)
async def get_simulation_config(
    factory_id: Optional[str] = Query(
        None,
        description=(
            "ID pabrik yang datanya dipakai untuk membangun konfigurasi simulasi. "
            "Kosongkan untuk memakai factory yang paling baru di-parse."
        ),
    ),
    db: AsyncSession = Depends(get_db),
) -> schemas.SimulationConfig:
    """
    Dipanggil oleh frontend di awal load (per factory aktif), sebelum tick
    loop lokal mulai jalan. Data diambil dari Digital Twin DB lewat
    `DigitalTwinService` -- sama seperti `GET /digital-twin` -- sehingga kedua
    API selalu konsisten. Jika belum ada factory yang berhasil di-parse,
    response otomatis jatuh ke konfigurasi seed statis bawaan.
    """
    return await service.get_simulation_config(db=db, factory_id=factory_id)