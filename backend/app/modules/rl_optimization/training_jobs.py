"""In-process RL training jobs: one CPU worker thread, one active job per factory.

Job state lives in memory and is mirrored to status.json next to the factory's RL
artifacts, so a status is still readable after a restart. Like app.worker.tasks this
requires running uvicorn with a single worker process.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from stable_baselines3.common.callbacks import BaseCallback

from app.core.config import settings
from app.optimization import scenario_store, train_ppo
from app.optimization.snapshot_from_db import RlInputError, load_rl_inputs
from app.services.snapshot_builder import SnapshotBuilder

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {"queued", "running"}
INPUT_FILES = ("factory_md", "worker_md", "init_state", "simulation_state", "simulation_summary")

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rl-train")
_shutdown = threading.Event()
_jobs: dict[str, "RlJob"] = {}
_latest_by_factory: dict[str, str] = {}
_tasks: set[asyncio.Task] = set()


def _now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)


@dataclass
class RlJob:
    """Mutable state of one RL training run."""

    factory_id: str
    total_timesteps: int
    has_simulation: bool
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "queued"
    progress_pct: float = 0.0
    error_message: Optional[str] = None
    submitted_at: datetime = field(default_factory=_now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the job into the OptimizationJobStatus shape."""
        return {
            "job_id": self.job_id,
            "factory_id": self.factory_id,
            "status": self.status,
            "progress_pct": round(self.progress_pct, 1),
            "error_message": self.error_message,
            "total_timesteps": self.total_timesteps,
            "has_simulation": self.has_simulation,
            "submitted_at": self.submitted_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }

    def persist(self) -> None:
        """Mirror the job state to status.json, ignoring filesystem errors."""
        try:
            scenario_store.write_json_atomic(
                scenario_store.rl_dir(self.factory_id) / "status.json", self.to_dict()
            )
        except OSError as error:
            logger.warning("Gagal menulis status RL %s: %s", self.job_id, error)


class ProgressCallback(BaseCallback):
    """Report training progress across the three scenarios and stop on shutdown."""

    def __init__(self, job: RlJob, scenario_index: int, scenario_count: int) -> None:
        super().__init__()
        self.job = job
        self.scenario_index = scenario_index
        self.scenario_count = scenario_count

    def _on_step(self) -> bool:
        """Update the job progress after every environment step."""
        fraction = min(1.0, self.num_timesteps / max(self.job.total_timesteps, 1))
        self.job.progress_pct = 100.0 * (self.scenario_index + fraction) / self.scenario_count * 0.97
        return not _shutdown.is_set()


def _train_blocking(job: RlJob, snapshot) -> None:
    """Calibrate, train all scenarios and export optimal_state.json; runs in the worker thread."""
    import torch

    job.status = "running"
    job.started_at = _now()
    job.persist()

    torch.set_num_threads(max(1, settings.RL_TORCH_THREADS))
    config = train_ppo.TrainingConfig(
        total_timesteps=job.total_timesteps,
        n_envs=max(1, settings.RL_N_ENVS),
        parallel_scenarios=False,
        eval_freq=0,
        output_dir=scenario_store.rl_dir(job.factory_id) / "training",
    )
    snapshot = train_ppo.calibrate_baselines(snapshot, seed=config.seed)
    scenario_count = len(train_ppo.SCENARIO_ORDER)
    models = train_ppo.train_all_scenarios(
        snapshot,
        config,
        callback_factory=lambda index, _: ProgressCallback(job, index, scenario_count),
    )
    if _shutdown.is_set():
        raise RuntimeError("Training dihentikan karena server dimatikan.")
    train_ppo.export_scenarios(
        snapshot=snapshot,
        models=models,
        output_path=scenario_store.artifact_path(job.factory_id),
        config=config,
        factory_id=job.factory_id,
    )


async def _run(job: RlJob, snapshot) -> None:
    """Run a job on the training thread and record its final status."""
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(_executor, _train_blocking, job, snapshot)
        job.status = "converged"
        job.progress_pct = 100.0
    except Exception as error:
        logger.exception("Training RL untuk factory %s gagal", job.factory_id)
        job.status = "failed"
        job.error_message = f"{type(error).__name__}: {error}"
    finally:
        job.finished_at = _now()
        job.persist()


def _write_inputs(factory_id: str, inputs: dict[str, Any]) -> None:
    """Store the mapped RL inputs so runs are reproducible from the CLI and readable by the chatbot."""
    directory = scenario_store.rl_dir(factory_id) / "inputs"
    for name in INPUT_FILES:
        path = directory / f"{name}.json"
        if inputs.get(name) is None:
            path.unlink(missing_ok=True)
        else:
            scenario_store.write_json_atomic(path, inputs[name])


async def enqueue(
    db: AsyncSession,
    factory_id: str,
    end_state: Optional[dict[str, Any]] = None,
    working_state: Optional[dict[str, Any]] = None,
    total_timesteps: Optional[int] = None,
) -> RlJob:
    """Validate the factory's RL inputs and schedule training, reusing an active job if any.

    Raises LookupError for an unknown factory and RlInputError when the twin cannot be
    turned into an RL snapshot.
    """
    active = _jobs.get(_latest_by_factory.get(factory_id, ""))
    if active is not None and active.status in ACTIVE_STATUSES:
        return active

    inputs = await load_rl_inputs(db, factory_id, end_state=end_state, working_state=working_state)
    try:
        snapshot = SnapshotBuilder(
            factory_md=inputs["factory_md"],
            worker_md=inputs["worker_md"],
            init_state=inputs["init_state"],
            simulation_state=inputs["simulation_state"],
        ).build()
    except (KeyError, ValueError, StopIteration) as error:
        raise RlInputError(f"Snapshot RL tidak valid: {error}") from error

    _write_inputs(factory_id, inputs)

    job = RlJob(
        factory_id=factory_id,
        total_timesteps=total_timesteps or settings.RL_TOTAL_TIMESTEPS,
        has_simulation=inputs["simulation_state"] is not None,
    )
    _jobs[job.job_id] = job
    _latest_by_factory[factory_id] = job.job_id
    job.persist()

    task = asyncio.create_task(_run(job, snapshot))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return job


def get_job(job_id: str) -> Optional[dict[str, Any]]:
    """Return the status of a job started by this process."""
    job = _jobs.get(job_id)
    return job.to_dict() if job else None


def get_factory_status(factory_id: str) -> Optional[dict[str, Any]]:
    """Return the latest RL job status of a factory from memory, status.json or the artifact."""
    job = _jobs.get(_latest_by_factory.get(factory_id, ""))
    if job is not None:
        return job.to_dict()

    has_result = scenario_store.load_optimization_result(factory_id) is not None
    stored = scenario_store.read_json(scenario_store.rl_dir(factory_id) / "status.json")
    if stored:
        if stored.get("status") in ACTIVE_STATUSES:
            stored["status"] = "converged" if has_result else "failed"
            stored["error_message"] = None if has_result else "Proses training terhenti sebelum selesai."
        return stored

    if has_result:
        return {
            "job_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"rl:{factory_id}")),
            "factory_id": factory_id,
            "status": "converged",
            "progress_pct": 100.0,
        }
    return None


def shutdown() -> None:
    """Ask a running training loop to stop and release the worker thread."""
    _shutdown.set()
    _executor.shutdown(wait=False, cancel_futures=True)


__all__ = ["RlInputError", "enqueue", "get_job", "get_factory_status", "shutdown"]
