"""
Background task runner untuk Tahap 5 (matriks kompatibilitas).

Tahap 5 memanggil agent LLM sebanyak (jumlah worker x jumlah job desk). Untuk
10 worker x 10 job desk itu 100 panggilan berantai di dalam satu request HTTP --
jauh melewati batas timeout reverse proxy pada umumnya. Modul ini memindahkan
eksekusinya keluar dari siklus request: endpoint hanya menuliskan satu baris
`compatibility_matrix_jobs` lalu langsung membalas 202, dan frontend melakukan
polling ke endpoint status.

CATATAN DEPLOYMENT: runner ini berjalan in-process memakai `asyncio.create_task`,
jadi state-nya milik satu proses uvicorn. Jalankan dengan `--workers 1`, atau
pindahkan `_execute_job()` ke Celery/arq (REDIS_URL sudah tersedia di settings)
bila butuh lebih dari satu proses. Konsekuensi konkretnya ada dua:
`mark_stale_jobs()` di startup akan menandai job milik proses lain sebagai
gagal, dan `cancel_job()` hanya bisa membatalkan job yang dimulai proses ini.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.db.session import AsyncSessionLocal
from app.modules.documents.exceptions import DocumentParserPipelineError
from app.modules.documents.models import CompatibilityMatrixJob

logger = logging.getLogger(__name__)

PROGRESS_FLUSH_SECONDS = 2.0

_running_tasks: dict[str, asyncio.Task] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ProgressCounter:
    """
    Penampung progres yang ditulis dari thread pool milik
    `generate_compatibility_matrix` dan dibaca dari event loop.

    Tidak memakai lock: kedua atribut hanya menampung int dan penugasannya
    atomik di bawah GIL, jadi pembaca paling buruk hanya melihat nilai yang
    tertinggal satu tick -- cukup untuk indikator progres.
    """

    __slots__ = ("completed", "total")

    def __init__(self) -> None:
        self.completed = 0
        self.total = 0

    def __call__(self, done: int, total: int) -> None:
        self.completed = done
        self.total = total


async def enqueue_compatibility_matrix(
    *,
    factory_id: str,
    max_workers: int = 4,
    max_attempts: int = 3,
    strict_compatibility: bool = False,
    persist: bool = True,
) -> CompatibilityMatrixJob:
    """Mendaftarkan job baru dan menjadwalkannya di event loop."""
    job_id = uuid.uuid4().hex

    async with AsyncSessionLocal() as session:
        job = CompatibilityMatrixJob(
            job_id=job_id,
            factory_id=factory_id,
            status="queued",
            max_workers=max_workers,
            max_attempts=max_attempts,
            strict_compatibility=strict_compatibility,
            persist_result=persist,
            failed_pairs=[],
            warnings=[],
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

    task = asyncio.create_task(_execute_job(job_id), name=f"compat-matrix-{job_id}")
    _running_tasks[job_id] = task
    task.add_done_callback(lambda _: _running_tasks.pop(job_id, None))

    return job


async def get_job(job_id: str) -> CompatibilityMatrixJob | None:
    async with AsyncSessionLocal() as session:
        return await session.get(CompatibilityMatrixJob, job_id)


async def list_jobs(
    factory_id: str | None = None, limit: int = 20, offset: int = 0
) -> list[CompatibilityMatrixJob]:
    stmt = (
        select(CompatibilityMatrixJob)
        .order_by(CompatibilityMatrixJob.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if factory_id:
        stmt = stmt.where(CompatibilityMatrixJob.factory_id == factory_id)

    async with AsyncSessionLocal() as session:
        return list((await session.execute(stmt)).scalars().all())


async def cancel_job(job_id: str) -> bool:
    """Membatalkan job yang masih berjalan di proses ini. True bila berhasil."""
    task = _running_tasks.get(job_id)
    if task is None or task.done():
        return False

    task.cancel()
    await _finalize(
        job_id,
        status="error",
        error_stage="cancelled",
        error_message="Job dibatalkan atas permintaan pengguna.",
    )
    return True


async def mark_stale_jobs() -> int:
    """
    Menandai job yang menggantung di status queued/running sebagai gagal.
    Dipanggil saat startup: proses yang menjalankannya sudah mati, jadi tidak
    akan pernah ada yang menyelesaikannya.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            update(CompatibilityMatrixJob)
            .where(CompatibilityMatrixJob.status.in_(["queued", "running"]))
            .values(
                status="error",
                error_stage="stale",
                error_message=(
                    "Proses backend berhenti saat job masih berjalan. "
                    "Jalankan ulang Tahap 5 untuk factory ini."
                ),
                finished_at=_now(),
            )
        )
        await session.commit()
        return result.rowcount or 0


async def _flush_progress(job_id: str, progress: ProgressCounter) -> None:
    """Menyalin progres in-memory ke DB berkala supaya polling terlihat hidup."""
    try:
        while True:
            await asyncio.sleep(PROGRESS_FLUSH_SECONDS)
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(CompatibilityMatrixJob)
                    .where(CompatibilityMatrixJob.job_id == job_id)
                    .values(
                        completed_pairs=progress.completed,
                        total_pairs=progress.total,
                    )
                )
                await session.commit()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Gagal menuliskan progres job %s", job_id)


async def _finalize(job_id: str, **values) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(CompatibilityMatrixJob)
            .where(CompatibilityMatrixJob.job_id == job_id)
            .values(finished_at=_now(), **values)
        )
        await session.commit()


async def _execute_job(job_id: str) -> None:
    # Import lokal: app.modules.documents.service menarik rantai modul yang
    # kembali menyentuh app.worker, jadi impor tingkat modul akan melingkar.
    from app.modules.documents import service

    async with AsyncSessionLocal() as session:
        job = await session.get(CompatibilityMatrixJob, job_id)
        if job is None:
            logger.warning("Job %s hilang sebelum sempat dijalankan.", job_id)
            return

        options = {
            "factory_id": job.factory_id,
            "max_workers": job.max_workers,
            "max_attempts": job.max_attempts,
            "strict_compatibility": job.strict_compatibility,
            "persist": job.persist_result,
        }
        job.status = "running"
        job.started_at = _now()
        await session.commit()

    progress = ProgressCounter()
    monitor = asyncio.create_task(_flush_progress(job_id, progress))

    try:
        async with AsyncSessionLocal() as session:
            result = await service.step_5_generate_compatibility_matrix(
                factory_id=options["factory_id"],
                db=session,
                max_workers=options["max_workers"],
                max_attempts=options["max_attempts"],
                strict_compatibility=options["strict_compatibility"],
                persist=options["persist"],
                progress=progress,
            )

        await _finalize(
            job_id,
            status="success",
            compatibility_matrix=result.get("compatibility_matrix"),
            evaluations_persisted=result.get("evaluations_persisted", 0),
            total_pairs=max(progress.total, result.get("pairs_evaluated", 0)),
            completed_pairs=result.get("pairs_evaluated", 0),
            failed_pairs=result.get("failed_pairs", []),
            warnings=result.get("warnings", []),
        )
        logger.info("Job matriks kompatibilitas %s selesai.", job_id)

    except asyncio.CancelledError:
        logger.info("Job matriks kompatibilitas %s dibatalkan.", job_id)
        raise

    except DocumentParserPipelineError as error:
        logger.warning("Job %s gagal pada tahap %s: %s", job_id, error.stage, error)
        await _finalize(
            job_id,
            status="error",
            error_stage=error.stage,
            error_message=str(error),
            error_details=getattr(error, "details", None) or None,
        )

    except Exception as error:
        logger.exception("Job %s gagal tanpa terduga.", job_id)
        await _finalize(
            job_id,
            status="error",
            error_stage="unknown",
            error_message=str(error),
        )

    finally:
        monitor.cancel()