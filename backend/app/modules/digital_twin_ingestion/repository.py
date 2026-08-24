# backend/app/modules/digital_twin_ingestion/repository.py
"""
Perubahan pada revisi ini:
1. FIX BUG KRITIS (FK violation `compatibility_evaluations.worker_id`): baris `workers`
   sebelumnya tidak pernah di-`flush()` sebelum `compatibility_evaluations` di-insert,
   karena satu-satunya flush di antara keduanya berada di dalam blok
   `if data.factory_flow_rightnow is not None:` yang SELALU dilewati pada pipeline
   kombinasi Tahap 1+2+4+5 (blok itu hanya diisi oleh Tahap 6 / Agent C). Akibatnya
   Postgres menolak insert compatibility_evaluations karena worker_id yang
   direferensikan belum benar-benar tersimpan di tabel `workers`.
   -> Ditambahkan `await self.db.flush()` eksplisit segera setelah loop `workers`,
      sebelum loop `llm_compatibility_and_evaluations`, terlepas dari apakah blok
      factory_flow_rightnow dieksekusi atau tidak.
2. FIX: `await self.db.commit()` di akhir method DIHAPUS. Method ini dipanggil oleh
   `documents/service.py` di dalam `async with db.begin_nested():` (savepoint
   terisolasi). Memanggil `commit()` di dalam savepoint tersebut tidak tepat --
   kontrol commit seharusnya sepenuhnya milik caller, yang memang sudah melakukan
   `await db.commit()` setelah blok ingestion selesai (menyatukan commit data
   Digital Twin dengan update audit trail `document_parse_jobs` secara atomik).
   Sebagai gantinya, method ini melakukan `flush()` di akhir agar seluruh objek
   tersimpan ke transaksi aktif (baik itu savepoint maupun sesi utama), namun
   commit final tetap menjadi tanggung jawab caller.
"""
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.digital_twin_ingestion import models, schemas


def _dump(obj: Any) -> dict[str, Any]:
    """Helper aman: dump model Pydantic atau lewatkan dict apa adanya."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return obj
    return {}


class DigitalTwinRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_full_snapshot(self, data: schemas.DigitalTwin) -> None:
        info = data.factory_info

        factory = models.Factory(
            factory_id=info.factory_id,
            factory_name=info.factory_name,
            process_type=info.process_type,
            declared_worker_count=info.declared_worker_count,
            registered_worker_count=info.registered_worker_count,
            layout_description=info.layout_description,
            workflow_sequence=info.workflow_sequence,
            process_edges=[_dump(pe) for pe in info.process_edges],
            entry_stages=info.entry_stages,
            terminal_stages=info.terminal_stages,
            parallel_groups=[_dump(pg) for pg in info.parallel_groups] if info.parallel_groups else None,
            lanes=info.lanes,
        )
        self.db.add(factory)

        for a in data.assets:
            self.db.add(models.Asset(
                asset_id=a.asset_id,
                factory_id=factory.factory_id,
                asset_name=a.asset_name,
                category=a.category,
                units_available=a.units_available,
                capacity_per_unit=_dump(a.capacity_per_unit),
                total_capacity=_dump(a.total_capacity),
                automation_level=a.automation_level,
                is_automated=a.is_automated,
                operational_cost_per_hour=a.operational_cost_per_hour,
                currency=a.currency,
                environmental_factors=_dump(a.environmental_factors),
                metric_derivation_reasoning=a.metric_derivation_reasoning,
            ))

        for s in data.process_stages:
            self.db.add(models.ProcessStage(
                stage_id=s.stage_id,
                factory_id=factory.factory_id,
                stage_name=s.stage_name,
                lane=s.lane,
                next_stage_id=s.next_stage_id,
                is_terminal=s.is_terminal,
                asset_id=s.asset_id,
                operator_task=s.operator_task,
                material_input=s.material_input,
                material_output=s.material_output,
                material_per_batch=[_dump(q) for q in s.material_per_batch],
                flow_type=s.flow_type,
                cycle_time_seconds=s.cycle_time_seconds,
                throughput=_dump(s.throughput),
                throughput_per_hour=s.throughput_per_hour,
                automation_level=s.automation_level,
                qc_requirement=s.qc_requirement,
                metric_derivation_reasoning=s.metric_derivation_reasoning,
            ))

        for sh in data.shifts:
            self.db.add(models.Shift(
                shift_id=sh.shift_id,
                factory_id=factory.factory_id,
                start_time=sh.start_time,
                end_time=sh.end_time,
                duration_hours=sh.duration_hours,
                crosses_midnight=sh.crosses_midnight,
            ))

        # process_stages & shifts wajib di-flush dulu karena job_desks
        # punya FK ke stage_id dan shift_id (ondelete RESTRICT butuh baris induk sudah ada)
        await self.db.flush()

        for j in data.job_desks:
            self.db.add(models.JobDesk(
                job_id=j.job_id,
                factory_id=factory.factory_id,
                allocation_id=j.allocation_id,
                job_title=j.job_title,
                stage_id=j.stage_id,
                assigned_asset_id=j.assigned_asset_id,
                assigned_worker_ids=j.assigned_worker_ids,
                shift_id=j.shift_id,
                headcount=j.headcount,
                demands=_dump(j.demands),
                qc_requirement=j.qc_requirement,
                metric_derivation_reasoning=j.metric_derivation_reasoning,
            ))

        for w in data.workers:
            self.db.add(models.Worker(
                worker_id=w.worker_id,
                factory_id=factory.factory_id,
                name=w.name,
                demographics=_dump(w.demographics),
                shift_context=_dump(w.shift_context),
                skills=w.skills,
                certifications=w.certifications,
                capabilities=w.capabilities,
            ))

        # FIX: job_desks & workers wajib di-flush di sini, TIDAK BOLEH bergantung pada
        # flush kondisional di dalam blok factory_flow_rightnow di bawah (blok itu
        # sering dilewati pada pipeline kombinasi Tahap 1+2+4+5). Tanpa flush ini,
        # insert `compatibility_evaluations` (yang mereferensikan worker_id) akan
        # gagal dengan ForeignKeyViolationError karena worker belum benar-benar
        # tersimpan di tabel `workers` pada saat itu.
        await self.db.flush()

        # factory_flow_rightnow opsional: pipeline Tahap 1+2+4+5 tidak mengisi ini
        # (hanya Tahap 6 / Agent C yang mengisi floor_state). Lewati bila None.
        if data.factory_flow_rightnow is not None:
            snapshot = models.FactoryFlowSnapshot(
                factory_id=factory.factory_id,
                snapshot_timestamp=data.factory_flow_rightnow.snapshot_timestamp,
                note=data.factory_flow_rightnow.note,
            )
            self.db.add(snapshot)
            await self.db.flush()  # perlu snapshot.id sebelum insert staff_positions

            for sp in data.factory_flow_rightnow.staff_current_positions:
                self.db.add(models.StaffPosition(
                    snapshot_id=snapshot.id,
                    factory_id=factory.factory_id,
                    worker_id=sp.worker_id,
                    current_station=sp.current_station,
                    current_asset_id=sp.current_asset_id,
                    activity_status=sp.activity_status,
                    moving_to_next_step=sp.moving_to_next_step,
                    handoff_item=sp.handoff_item,
                ))

        for ev in data.llm_compatibility_and_evaluations:
            self.db.add(models.CompatibilityEvaluation(
                factory_id=factory.factory_id,
                worker_id=ev.worker_id,
                job_id=ev.job_id,
                asset_id=ev.asset_id,
                evaluations=_dump(ev.evaluations),
                llm_reasoning=ev.llm_reasoning,
            ))

        # FIX: commit() dihapus dari sini -- kontrol transaksi/commit sepenuhnya
        # menjadi tanggung jawab caller (documents/service.py), yang memanggil
        # method ini di dalam `async with db.begin_nested():` (savepoint terisolasi)
        # lalu melakukan `await db.commit()` sendiri setelah blok ingestion selesai,
        # menyatukan commit data Digital Twin dengan update audit trail
        # `document_parse_jobs` secara atomik. flush() di sini memastikan seluruh
        # objek pending tersimpan ke transaksi aktif tanpa mengunci/menutup transaksi
        # tersebut lebih awal.
        await self.db.flush()