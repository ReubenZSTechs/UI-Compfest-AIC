"""
Pydantic schemas untuk simulation config.

Backend TIDAK menjalankan tick/state machine simulasi -- itu tetap jalan di
frontend (persis logic yang sudah ada di `simulationApi.mock.ts`). Backend
hanya menyediakan data konfigurasi (recipe table, kapasitas, worker seed,
jadwal shift, dst.) supaya angka-angka itu tidak lagi hardcoded di frontend
dan bisa diubah dari satu tempat (mis. lewat DB/admin panel nantinya).
"""
from typing import Literal

from pydantic import BaseModel

BurnoutRisk = Literal["low", "medium", "high"]


class MaterialTemplate(BaseModel):
    name: str
    unit: str


class RealtimeMetrics(BaseModel):
    current_fatigue_level: float
    current_stress_level: float
    effective_throughput_per_hour: float
    effective_error_probability: float
    burnout_hazard_risk: BurnoutRisk
    throughput_multiplier: float


class SeedAssignment(BaseModel):
    worker_id: str
    assigned_job_id: str
    assigned_asset_id: str
    calculated_realtime_metrics: RealtimeMetrics


class SimulationConfig(BaseModel):
    """
    Satu-satunya sumber kebenaran untuk parameter simulasi. Frontend fetch ini
    SEKALI di awal (sebelum simulasi jalan), lalu jalankan tick loop-nya sendiri
    persis seperti versi mock, tapi pakai angka-angka dari sini.

    Key dict di bawah adalah "ordinal" step (1..10), dikirim sebagai object JSON
    biasa -- TypeScript `Record<number, T>` kamu bisa langsung pakai ini tanpa
    transform apapun karena JS object key numerik otomatis jadi string juga.
    """
    # --- per-station recipe/capacity table ---
    materials_by_ordinal: dict[int, MaterialTemplate]
    step_names: dict[int, str]
    step_cost_base: dict[int, int]
    capacity_by_ordinal: dict[int, float]
    batch_in_by_ordinal: dict[int, float]
    batch_out_by_ordinal: dict[int, float]
    cycle_ticks_by_ordinal: dict[int, int]

    # --- thresholds / tuning ---
    bottleneck_fill_threshold: float
    idle_qty_threshold: float
    station_1_safety_margin: float

    # --- warehouse ---
    warehouse_capacity: float
    warehouse_feed_rate: float
    warehouse_step_id: str

    # --- workers ---
    worker_throughput_multiplier: dict[str, float]
    seed_assignments: list[SeedAssignment]

    # --- shift schedule (dalam menit, elapsed dari shift_start) ---
    shift_start_minutes: int
    break_start_elapsed: int
    break_end_elapsed: int
    shift_end_elapsed: int

    # --- misc ---
    analytical_insight_summary: str
    target_output_units: float
    initial_batch_seq: int