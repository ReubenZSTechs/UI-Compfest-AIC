from app.modules.digital_twin_ingestion import schemas


def _quantity(value, unit="pcs/jam"):
    """Build a Quantity with a numeric value."""
    return schemas.Quantity(raw=f"{value} {unit}", value=value, unit=unit)


def make_twin() -> schemas.DigitalTwin:
    """Build a small four-station, six-worker digital twin for tests."""
    stage_ids = ["mixing", "forming", "baking", "packing"]
    rates = [120.0, 90.0, 60.0, 150.0]
    assets = []
    stages = []
    jobs = []
    for index, (stage_id, rate) in enumerate(zip(stage_ids, rates)):
        asset_id = f"ast-{stage_id}"
        assets.append(
            schemas.Asset(
                asset_id=asset_id,
                asset_name=stage_id.title(),
                category="machine",
                units_available=1,
                capacity_per_unit=_quantity(rate),
                total_capacity=_quantity(rate),
                automation_level="manual",
                is_automated=False,
                operational_cost_per_hour=50_000.0,
                currency="IDR",
                environmental_factors=schemas.AssetEnvironmentalFactors(
                    noise_level_db=None if index == 0 else 70.0,
                    vibration_hazard_level="medium",
                    physical_strain_index=0.4,
                ),
            )
        )
        stages.append(
            schemas.ProcessStage(
                stage_id=stage_id,
                stage_name=stage_id.title(),
                lane="main",
                next_stage_id=stage_ids[index + 1] if index + 1 < len(stage_ids) else None,
                is_terminal=index + 1 == len(stage_ids),
                asset_id=asset_id,
                operator_task="operate",
                flow_type="batch",
                cycle_time_seconds=3600.0 / rate,
                throughput=_quantity(rate),
                throughput_per_hour=rate,
                automation_level="manual",
                qc_requirement="visual",
            )
        )
        jobs.append(
            schemas.JobDesk(
                job_id=f"job-{stage_id}",
                allocation_id=f"alloc-{stage_id}",
                job_title=f"Operator {stage_id}",
                stage_id=stage_id,
                assigned_asset_id=asset_id,
                assigned_worker_ids=[f"wrk-{index * 2 + 1:02d}", f"wrk-{index * 2 + 2:02d}"]
                if stage_id == "baking"
                else [f"wrk-{index * 2 + 1:02d}"],
                shift_id="shift-1",
                headcount=1,
                demands=schemas.Demands(
                    required_cognitive_focus=0.6,
                    physical_demand_level="high",
                    task_complexity=0.5,
                    error_severity="high",
                ),
                qc_requirement="visual",
            )
        )
    workers = [
        schemas.Worker(
            worker_id=f"wrk-{number:02d}",
            name=f"Pekerja {number}",
            demographics=schemas.Demographics(
                age=25 + number,
                gender="L",
                years_of_experience=number,
                baseline_physical_stamina=0.5 + number * 0.05,
                cognitive_resilience=0.7,
            ),
            shift_context=schemas.ShiftContext(hours_worked_today=2, consecutive_shifts=1),
        )
        for number in range(1, 9)
    ]
    evaluations = [
        schemas.CompatibilityEvaluation(
            worker_id="wrk-01",
            job_id="job-mixing",
            evaluations={
                "overall_compatibility_score": 0.9,
                "throughput_multiplier": 1.1,
                "error_multiplier": 0.6,
                "fatigue_accumulation_rate": 0.8,
                "stress_sensitivity_factor": 0.5,
            },
        ),
        schemas.CompatibilityEvaluation(
            worker_id="wrk-03",
            job_id="job-forming",
            evaluations={
                "overall_compatibility_score": 0.4,
                "throughput_multiplier": 0.9,
                "error_multiplier": 1.2,
            },
        ),
    ]
    return schemas.DigitalTwin(
        factory_info=schemas.FactoryInfo(
            factory_id="fac-test",
            factory_name="Pabrik Roti Uji",
            process_type="serial",
            declared_worker_count=8,
            registered_worker_count=8,
            layout_description="serial",
            workflow_sequence=stage_ids,
        ),
        assets=assets,
        process_stages=stages,
        job_desks=jobs,
        workers=workers,
        llm_compatibility_and_evaluations=evaluations,
    )


def make_runtime(state: str, speed: float) -> dict:
    """Build a browser LiveSimulationState with worker_runtime for the test twin."""
    runtime = []
    for worker_id, job_id, step_id in [
        ("wrk-01", "job-mixing", "mixing"),
        ("wrk-03", "job-forming", "forming"),
        ("wrk-05", "job-baking", "baking"),
        ("wrk-06", "job-baking", "baking"),
        ("wrk-07", "job-packing", "packing"),
        ("wrk-99", "job-baking", "baking"),
    ]:
        runtime.append(
            {
                "worker_id": worker_id,
                "worker_name": worker_id,
                "assigned_job_id": job_id,
                "assigned_step_id": step_id,
                "shift_id": "shift-1",
                "state": state,
                "compatibility_score": 0.7,
                "speed_factor": speed,
                "metrics": {
                    "current_fatigue_level": 0.4,
                    "current_stress_level": 0.3,
                    "effective_throughput_per_hour": 10.0,
                    "effective_error_probability": 0.02,
                    "burnout_hazard_risk": "medium",
                    "throughput_multiplier": 1.0,
                },
            }
        )
    return {
        "live_simulation_state": {
            "worker_runtime": runtime,
            "system_bottlenecks": ["baking"],
            "simulation_summary": {"total_output_units": 400},
            "analytical_insight_summary": "Baking menjadi bottleneck.",
            "shift_info": {"is_shift_ended": state == "off_shift"},
        }
    }
