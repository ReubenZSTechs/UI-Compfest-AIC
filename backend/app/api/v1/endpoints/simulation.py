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
module scope), bukan berulang/polling -- karena isinya konfigurasi statis,
bukan live state.
"""
from fastapi import APIRouter

from app.modules.simulation import schemas, service

router = APIRouter()


@router.get(
    "/config",
    response_model=schemas.SimulationConfig,
    summary="Ambil konfigurasi statis simulasi (recipe table, kapasitas, worker seed, jadwal shift)",
)
async def get_simulation_config() -> schemas.SimulationConfig:
    """
    Dipanggil sekali oleh frontend di awal load, sebelum tick loop lokal mulai
    jalan. Response ini TIDAK berubah antar request (stateless) -- kalau nanti
    recipe/kapasitas mau dibuat dinamis, cukup ubah `service.get_simulation_config()`
    untuk query DB, signature endpoint ini tetap sama.
    """
    return service.get_simulation_config()