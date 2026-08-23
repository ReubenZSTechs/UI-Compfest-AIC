# app/api/v1/endpoints/rl_optimization.py
"""
Endpoint untuk domain RL Optimization.

Mencakup:
- Digital Twin snapshot (factory_info, assets, job_descriptions, workers) --
  Fase Inisialisasi untuk `features/simulation_optimisation` frontend.
- Trigger & monitoring proses training/inference RL (Maskable PPO) --
  compute berat yang GENUINELY berjalan di backend (bukan tick simulasi).
- Hasil skenario optimasi (Pareto-optimal scenarios)
- Terapkan (apply) skenario terpilih -- menulis ulang posisi staf di DB

REVISI (arsitektur Client-Side Simulation):
`GET /simulation/live` dan `GET /simulation/live/bottlenecks` SUDAH DIHAPUS.
Endpoint tersebut dulunya menyiratkan backend menghitung "live simulation
state" (fatigue/stress/throughput real-time) -- padahal implementasinya
selalu stub (`NotImplementedError`), dan frontend
(`features/simulation_optimisation/api/simulationApi.ts` ->
`fetchLiveSimulationState()`) sudah 100% menjalankan tick simulasi ini
secara lokal di browser (jitter-based, tanpa network call). Backend hanya
perlu menyediakan `GET /digital-twin` di bawah sebagai bahan mentah untuk
initial state, asset config, dan constraint model -- frontend yang
membangun & menjalankan simulasinya sendiri dari situ.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_db, get_current_user
from app.modules.rl_optimization import schemas, service

router = APIRouter()


# Digital Twin — Single Source of Truth

@router.get(
    "/digital-twin",
    response_model=schemas.DigitalTwinResponse,
    summary="Ambil snapshot lengkap Digital Twin (factory_info, assets, job_descriptions, workers)",
)
async def get_digital_twin(
    factory_id: str,
    db=Depends(get_db),
):
    """
    Mengambil struktur Digital Twin terkini untuk satu factory:
    - factory_info (workflow_sequence)
    - assets (karakteristik hardware)
    - job_descriptions (tuntutan kualitatif tugas)
    - workers (demografi & shift context)
    - llm_compatibility_and_evaluations (matriks kompatibilitas N x M)
    """
    twin = await service.get_digital_twin(db, factory_id=factory_id)
    if twin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Digital twin untuk factory_id '{factory_id}' tidak ditemukan.",
        )
    return twin


@router.put(
    "/digital-twin",
    response_model=schemas.DigitalTwinResponse,
    summary="Update / replace Digital Twin (mis. hasil re-parsing dokumen sumber via LLM)",
)
async def upsert_digital_twin(
    payload: schemas.DigitalTwinUpsertRequest,
    db=Depends(get_db),
):
    """
    Dipakai saat LLM Text Parser menghasilkan JSON digital twin baru
    (mis. ada perubahan assets/job_descriptions dari dokumen sumber).
    """
    return await service.upsert_digital_twin(db, payload=payload)


# RL Optimization Job — pola asynchronous (training bisa berjalan lama)

@router.post(
    "/optimize",
    response_model=schemas.OptimizationJobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger proses training/inference RL (Maskable PPO) secara async",
)
async def trigger_optimization(
    payload: schemas.OptimizationRequest,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Tidak menjalankan training secara blocking di request ini.
    Job didorong ke background worker (Celery/arq), endpoint langsung
    mengembalikan job_id untuk dipoll lewat GET /optimize/{job_id}.
    """
    job = await service.enqueue_optimization_job(
        db,
        factory_id=payload.factory_id,
        constraints=payload.constraints,
        requested_by=current_user.id,
    )
    return job


@router.get(
    "/optimize/{job_id}",
    response_model=schemas.OptimizationJobStatus,
    summary="Cek status job optimasi (queued / running / converged / failed)",
)
async def get_optimization_job_status(
    job_id: UUID,
    db=Depends(get_db),
):
    """
    Status mengikuti siklus training:
    queued -> running -> converged (RL CONVERGED) / failed
    """
    job = await service.get_job_status(db, job_id=job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job optimasi '{job_id}' tidak ditemukan.",
        )
    return job


@router.get(
    "/optimize/{job_id}/scenarios",
    response_model=list[schemas.OptimizationScenario],
    summary="Ambil hasil skenario Pareto-optimal dari job yang sudah selesai",
)
async def get_optimization_scenarios(
    job_id: UUID,
    db=Depends(get_db),
):
    """
    Mengembalikan 3 skenario (mis. Realokasi SDM Murni, Substitusi Otomasi,
    Full Optimization), masing-masing dengan metrics before/after,
    factory_flow_optimal, dan rl_reasoning.
    """
    scenarios = await service.get_scenarios(db, job_id=job_id)
    if not scenarios:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Belum ada skenario untuk job '{job_id}' (mungkin belum converged).",
        )
    return scenarios


@router.get(
    "/optimize/{job_id}/scenarios/{scenario_id}",
    response_model=schemas.OptimizationScenario,
    summary="Ambil detail satu skenario spesifik",
)
async def get_optimization_scenario_detail(
    job_id: UUID,
    scenario_id: str,
    db=Depends(get_db),
):
    scenario = await service.get_scenario_detail(
        db, job_id=job_id, scenario_id=scenario_id
    )
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skenario '{scenario_id}' tidak ditemukan pada job '{job_id}'.",
        )
    return scenario


# Terapkan skenario terpilih ke kondisi live

@router.post(
    "/optimize/{job_id}/scenarios/{scenario_id}/apply",
    response_model=schemas.ApplyScenarioResponse,
    summary="Terapkan reallocation_moves dari skenario terpilih ke live simulation state",
)
async def apply_scenario(
    job_id: UUID,
    scenario_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Menulis ulang staff_current_positions sesuai optimal_staff_positions
    pada skenario terpilih (mis. swap wrk-07 <-> wrk-09 pada scenario_01).
    Idealnya dibungkus transaksi DB agar atomic.
    """
    result = await service.apply_scenario(
        db,
        job_id=job_id,
        scenario_id=scenario_id,
        applied_by=current_user.id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Skenario tidak valid atau tidak dapat diterapkan.",
        )
    return result