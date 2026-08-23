# backend/app/modules/simulation/service.py
"""
Service layer untuk simulation module.

Backend di sini stateless -- tidak ada engine/tick loop, tidak ada lock,
tidak ada state yang berubah antar request. `get_simulation_config()` cuma
merakit data dari `constants.py` jadi bentuk response yang dipakai frontend.

Kalau nanti recipe/kapasitas/worker seed mau dibuat dinamis (mis. diedit dari
admin panel dan disimpan di DB), tinggal ganti isi fungsi ini untuk query DB
alih-alih baca dari constants.py -- signature & response shape-nya tetap sama.
"""
from . import constants as C
from .schemas import MaterialTemplate, SeedAssignment, RealtimeMetrics, SimulationConfig


def _build_seed_assignments() -> list[SeedAssignment]:
    raw = [
        ("wrk-01", "job-01", "ast-01", dict(current_fatigue_level=0.2, current_stress_level=0.18, effective_throughput_per_hour=300.0, effective_error_probability=0.01, burnout_hazard_risk="low"), "wrk-01"),
        ("wrk-02", "job-02", "ast-02", dict(current_fatigue_level=0.25, current_stress_level=0.22, effective_throughput_per_hour=165.0, effective_error_probability=0.014, burnout_hazard_risk="low"), "wrk-02"),
        ("wrk-03", "job-03", "ast-03", dict(current_fatigue_level=0.35, current_stress_level=0.25, effective_throughput_per_hour=200.0, effective_error_probability=0.018, burnout_hazard_risk="low"), "wrk-03"),
        ("wrk-04", "job-04", "ast-04", dict(current_fatigue_level=0.3, current_stress_level=0.2, effective_throughput_per_hour=216.0, effective_error_probability=0.015, burnout_hazard_risk="low"), "wrk-04"),
        ("wrk-05", "job-05", "ast-05", dict(current_fatigue_level=0.22, current_stress_level=0.24, effective_throughput_per_hour=189.0, effective_error_probability=0.016, burnout_hazard_risk="low"), "wrk-05"),
        ("wrk-13", "job-05", "ast-05", dict(current_fatigue_level=0.22, current_stress_level=0.24, effective_throughput_per_hour=189.0, effective_error_probability=0.016, burnout_hazard_risk="low"), "wrk-05"),
        ("wrk-14", "job-05", "ast-05", dict(current_fatigue_level=0.22, current_stress_level=0.24, effective_throughput_per_hour=189.0, effective_error_probability=0.016, burnout_hazard_risk="low"), "wrk-05"),
        ("wrk-15", "job-05", "ast-05", dict(current_fatigue_level=0.22, current_stress_level=0.24, effective_throughput_per_hour=189.0, effective_error_probability=0.016, burnout_hazard_risk="low"), "wrk-05"),
        ("wrk-16", "job-05", "ast-05", dict(current_fatigue_level=0.22, current_stress_level=0.24, effective_throughput_per_hour=189.0, effective_error_probability=0.016, burnout_hazard_risk="low"), "wrk-05"),
        ("wrk-06", "job-06", "ast-06", dict(current_fatigue_level=0.18, current_stress_level=0.3, effective_throughput_per_hour=250.0, effective_error_probability=0.008, burnout_hazard_risk="low"), "wrk-06"),
        ("wrk-11", "job-06", "ast-06", dict(current_fatigue_level=0.20, current_stress_level=0.22, effective_throughput_per_hour=240.0, effective_error_probability=0.01, burnout_hazard_risk="low"), "wrk-11"),
        ("wrk-07", "job-07", "ast-07", dict(current_fatigue_level=0.72, current_stress_level=0.58, effective_throughput_per_hour=253.0, effective_error_probability=0.03, burnout_hazard_risk="high"), "wrk-07"),
        ("wrk-12", "job-07", "ast-07", dict(current_fatigue_level=0.15, current_stress_level=0.18, effective_throughput_per_hour=260.0, effective_error_probability=0.009, burnout_hazard_risk="low"), "wrk-12"),
        ("wrk-08", "job-08", "ast-08", dict(current_fatigue_level=0.12, current_stress_level=0.15, effective_throughput_per_hour=209.0, effective_error_probability=0.012, burnout_hazard_risk="low"), "wrk-08"),
        ("wrk-09", "job-09", "ast-09", dict(current_fatigue_level=0.28, current_stress_level=0.26, effective_throughput_per_hour=200.0, effective_error_probability=0.011, burnout_hazard_risk="low"), "wrk-09"),
        ("wrk-10", "job-10", "ast-10", dict(current_fatigue_level=0.1, current_stress_level=0.14, effective_throughput_per_hour=204.0, effective_error_probability=0.01, burnout_hazard_risk="low"), "wrk-10"),
    ]
    return [
        SeedAssignment(
            worker_id=worker_id,
            assigned_job_id=job_id,
            assigned_asset_id=asset_id,
            calculated_realtime_metrics=RealtimeMetrics(
                **base, throughput_multiplier=C.WORKER_THROUGHPUT_MULTIPLIER.get(mult_key, 1.0)
            ),
        )
        for worker_id, job_id, asset_id, base, mult_key in raw
    ]


def get_simulation_config() -> SimulationConfig:
    return SimulationConfig(
        materials_by_ordinal={
            ordinal: MaterialTemplate(**tpl) for ordinal, tpl in C.MATERIAL_BY_ORDINAL.items()
        },
        step_names=C.STEP_NAMES,
        step_cost_base=C.STEP_COST_BASE,
        capacity_by_ordinal=C.CAPACITY_BY_ORDINAL,
        batch_in_by_ordinal=C.BATCH_IN_BY_ORDINAL,
        batch_out_by_ordinal=C.BATCH_OUT_BY_ORDINAL,
        cycle_ticks_by_ordinal=C.CYCLE_TICKS_BY_ORDINAL,
        bottleneck_fill_threshold=C.BOTTLENECK_FILL_THRESHOLD,
        idle_qty_threshold=C.IDLE_QTY_THRESHOLD,
        station_1_safety_margin=C.STATION_1_SAFETY_MARGIN,
        warehouse_capacity=C.WAREHOUSE_CAPACITY,
        warehouse_feed_rate=C.WAREHOUSE_FEED_RATE,
        warehouse_step_id=C.WAREHOUSE_STEP_ID,
        worker_throughput_multiplier=C.WORKER_THROUGHPUT_MULTIPLIER,
        seed_assignments=_build_seed_assignments(),
        shift_start_minutes=C.SHIFT_START_MINUTES,
        break_start_elapsed=C.BREAK_START_ELAPSED,
        break_end_elapsed=C.BREAK_END_ELAPSED,
        shift_end_elapsed=C.SHIFT_END_ELAPSED,
        analytical_insight_summary=C.INSIGHT,
        target_output_units=C.TARGET_OUTPUT_UNITS,
        initial_batch_seq=232,
    )