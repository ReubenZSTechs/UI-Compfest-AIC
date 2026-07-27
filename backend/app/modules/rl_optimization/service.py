# app/modules/rl_optimization/service.py
"""
STUB — implementasi penuh menyusul.

File ini sengaja berisi fungsi placeholder dengan signature final,
supaya endpoint di api/v1/endpoints/rl_optimization.py bisa di-import
dan app bisa di-run untuk pengecekan infra dasar (routing, DB
connection, dsb) sebelum business logic sungguhan ditulis.
"""

from uuid import UUID

from app.modules.rl_optimization import schemas


async def get_digital_twin(db, factory_id: str) -> schemas.DigitalTwinResponse | None:
    raise NotImplementedError


async def upsert_digital_twin(db, payload: schemas.DigitalTwinUpsertRequest) -> schemas.DigitalTwinResponse:
    raise NotImplementedError


async def get_live_state(db, factory_id: str) -> schemas.LiveSimulationResponse | None:
    raise NotImplementedError


async def get_bottlenecks(db, factory_id: str) -> list[schemas.BottleneckInsight]:
    raise NotImplementedError


async def enqueue_optimization_job(db, factory_id: str, constraints, requested_by: str) -> schemas.OptimizationJobAccepted:
    raise NotImplementedError


async def get_job_status(db, job_id: UUID) -> schemas.OptimizationJobStatus | None:
    raise NotImplementedError


async def get_scenarios(db, job_id: UUID) -> list[schemas.OptimizationScenario]:
    raise NotImplementedError


async def get_scenario_detail(db, job_id: UUID, scenario_id: str) -> schemas.OptimizationScenario | None:
    raise NotImplementedError


async def apply_scenario(db, job_id: UUID, scenario_id: str, applied_by: str) -> schemas.ApplyScenarioResponse | None:
    raise NotImplementedError
