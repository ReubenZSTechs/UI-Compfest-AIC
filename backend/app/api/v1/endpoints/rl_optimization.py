"""RL optimization endpoints: digital twin view, on-demand Maskable PPO training and its scenarios."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.modules.rl_optimization import schemas, service, training_jobs
from app.optimization import scenario_store
from app.optimization.snapshot_from_db import RlInputError

router = APIRouter()


@router.get(
    "/digital-twin",
    response_model=schemas.DigitalTwinResponse,
    summary="Ambil snapshot Digital Twin dalam bentuk yang dipakai modul RL",
)
async def get_digital_twin(factory_id: str, db: AsyncSession = Depends(get_db)):
    """Return factory_info, assets, job_descriptions, workers and compatibility for a factory."""
    twin = await service.get_digital_twin(db, factory_id=factory_id)
    if twin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Digital twin untuk factory_id '{factory_id}' tidak ditemukan.",
        )
    return twin


@router.post(
    "/{factory_id}/optimize",
    response_model=schemas.OptimizationJobStatus,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Mulai training RL dari digital twin dan hasil simulasi terakhir",
)
async def start_factory_optimization(
    factory_id: str,
    payload: schemas.RlOptimizeRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Map the twin and posted simulation state onto RL inputs and train in the background."""
    payload = payload or schemas.RlOptimizeRequest()
    timesteps = payload.total_timesteps
    if timesteps is not None:
        timesteps = min(timesteps, settings.RL_MAX_TIMESTEPS)
    try:
        job = await training_jobs.enqueue(
            db,
            factory_id,
            end_state=payload.end_state,
            working_state=payload.working_state,
            total_timesteps=timesteps,
        )
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except RlInputError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    return job.to_dict()


@router.get(
    "/{factory_id}/optimize/status",
    response_model=schemas.OptimizationJobStatus,
    summary="Status training RL terakhir untuk satu factory",
)
async def get_factory_optimization_status(factory_id: str):
    """Return queued / running / converged / failed for the latest run of a factory."""
    job = training_jobs.get_factory_status(factory_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Belum ada training RL untuk factory '{factory_id}'.",
        )
    return job


@router.get(
    "/optimize/{job_id}",
    response_model=schemas.OptimizationJobStatus,
    summary="Status satu job training RL",
)
async def get_optimization_job_status(job_id: str):
    """Return the status of a job started by this server process."""
    job = training_jobs.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job optimasi '{job_id}' tidak ditemukan.",
        )
    return job


@router.get(
    "/{factory_id}/scenarios",
    response_model=schemas.RlScenarioBundle,
    summary="Ambil ketiga skenario hasil training RL untuk satu factory",
)
async def get_factory_optimization_scenarios(factory_id: str):
    """Return scenario_01..03 exported by the latest finished training of a factory."""
    bundle = scenario_store.load_optimization_result(factory_id)
    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hasil optimasi RL untuk factory '{factory_id}' belum tersedia.",
        )
    return bundle
