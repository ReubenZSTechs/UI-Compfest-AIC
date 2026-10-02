"""Digital twin view for the RL module, read from the canonical digital twin tables."""

from app.modules.rl_optimization import schemas


def _to_rl_digital_twin(twin, factory_id: str) -> schemas.DigitalTwinResponse:
    """Memetakan `digital_twin_ingestion.schemas.DigitalTwin` (sumber data
    kanonik) ke bentuk `rl_optimization.schemas.DigitalTwinResponse` yang
    dipakai frontend `simulation_optimisation` untuk membangun initial
    state-nya sendiri (menggantikan `SEED_STATE` hardcoded)."""
    stage_by_asset_id = {s.asset_id: s for s in twin.process_stages}

    assets = []
    for a in twin.assets:
        stage = stage_by_asset_id.get(a.asset_id)
        assets.append(
            schemas.Asset(
                asset_id=a.asset_id,
                asset_name=a.asset_name,
                category=a.category,
                workflow_step=stage.stage_id if stage else "",
                is_automated=a.is_automated,
                base_throughput_capacity=(
                    stage.throughput_per_hour
                    if stage and stage.throughput_per_hour
                    else (a.total_capacity.value or 0.0)
                ),
                operational_cost_per_hour=a.operational_cost_per_hour,
                environmental_factors=schemas.EnvironmentalFactors(
                    noise_level_db=a.environmental_factors.noise_level_db,
                    vibration_hazard_level=a.environmental_factors.vibration_hazard_level,
                    physical_strain_index=a.environmental_factors.physical_strain_index,
                ),
                metric_derivation_reasoning=a.metric_derivation_reasoning or "",
            )
        )

    job_descriptions = [
        schemas.JobDesk(
            job_id=jd.job_id,
            job_title=jd.job_title,
            workflow_step=jd.stage_id,
            assigned_asset_id=jd.assigned_asset_id,
            demands=schemas.JobDemands(**jd.demands.model_dump()),
            qc_requirement=jd.qc_requirement,
            metric_derivation_reasoning=jd.metric_derivation_reasoning or "",
        )
        for jd in twin.job_desks
    ]

    workers = [
        schemas.Worker(
            worker_id=w.worker_id,
            name=w.name,
            demographics=schemas.WorkerDemographics(**w.demographics.model_dump()),
            shift_context=schemas.WorkerShiftContext(**w.shift_context.model_dump()),
        )
        for w in twin.workers
    ]

    compatibility_entries = []
    for ce in twin.llm_compatibility_and_evaluations:
        evals = ce.evaluations
        evals_dict = evals.model_dump() if hasattr(evals, "model_dump") else dict(evals)
        compatibility_entries.append(
            schemas.CompatibilityEntry(
                worker_id=ce.worker_id,
                job_id=ce.job_id,
                asset_id=ce.asset_id or "",
                evaluations=schemas.CompatibilityEvaluation(
                    overall_compatibility_score=evals_dict.get("overall_compatibility_score", 0.0),
                    throughput_multiplier=evals_dict.get("throughput_multiplier", 1.0),
                    error_multiplier=evals_dict.get("error_multiplier", 1.0),
                    fatigue_accumulation_rate=evals_dict.get("fatigue_accumulation_rate"),
                    stress_sensitivity_factor=evals_dict.get("stress_sensitivity_factor"),
                ),
                llm_reasoning=ce.llm_reasoning or "",
            )
        )

    return schemas.DigitalTwinResponse(
        factory_info=schemas.FactoryInfo(
            factory_id=twin.factory_info.factory_id,
            factory_name=twin.factory_info.factory_name,
            workflow_sequence=twin.factory_info.workflow_sequence,
        ),
        assets=assets,
        job_descriptions=job_descriptions,
        workers=workers,
        llm_compatibility_and_evaluations=compatibility_entries,
        updated_at=None,
    )


async def get_digital_twin(db, factory_id: str) -> schemas.DigitalTwinResponse | None:
    """Return the RL-shaped digital twin of a factory, or None when it has no stages."""
    from app.modules.digital_twin_ingestion.service import DigitalTwinService

    twin = await DigitalTwinService(db).get_full_twin(factory_id)
    if not twin.process_stages and not twin.factory_info.workflow_sequence:
        return None
    return _to_rl_digital_twin(twin, factory_id)
