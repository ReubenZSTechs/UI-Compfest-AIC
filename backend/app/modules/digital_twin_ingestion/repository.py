from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.digital_twin_ingestion import models, schemas


class DigitalTwinRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_full_snapshot(self, data: schemas.DigitalTwin) -> None:
        factory = models.Factory(
            factory_id=data.factory_info.factory_id,
            factory_name=data.factory_info.factory_name,
            workflow_sequence=data.factory_info.workflow_sequence,
        )
        self.db.add(factory)

        for a in data.assets:
            self.db.add(models.Asset(
                asset_id=a.asset_id,
                factory_id=factory.factory_id,
                asset_name=a.asset_name,
                category=a.category,
                workflow_step=a.workflow_step,
                is_automated=a.is_automated,
                base_throughput_capacity=a.base_throughput_capacity,
                operational_cost_per_hour=a.operational_cost_per_hour,
                environmental_factors=a.environmental_factors.model_dump(),
                metric_derivation_reasoning=a.metric_derivation_reasoning,
            ))

        for j in data.job_desks:
            self.db.add(models.JobDesk(
                job_id=j.job_id,
                factory_id=factory.factory_id,
                job_title=j.job_title,
                workflow_step=j.workflow_step,
                assigned_asset_id=j.assigned_asset_id,
                demands=j.demands.model_dump(),
                qc_requirement=j.qc_requirement,
                metric_derivation_reasoning=j.metric_derivation_reasoning,
            ))

        for w in data.workers:
            self.db.add(models.Worker(
                worker_id=w.worker_id,
                factory_id=factory.factory_id,
                name=w.name,
                demographics=w.demographics.model_dump(),
                shift_context=w.shift_context.model_dump(),
            ))

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
                evaluations=ev.evaluations.model_dump(),
                llm_reasoning=ev.llm_reasoning,
            ))

        await self.db.commit()