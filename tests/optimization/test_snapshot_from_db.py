import pytest

from app.optimization.snapshot_from_db import RlInputError, build_rl_inputs
from app.services.snapshot_builder import SnapshotBuilder

from .fixtures import make_runtime, make_twin


def _build(inputs):
    """Run SnapshotBuilder on mapped inputs."""
    return SnapshotBuilder(
        factory_md=inputs["factory_md"],
        worker_md=inputs["worker_md"],
        init_state=inputs["init_state"],
        simulation_state=inputs["simulation_state"],
    ).build()


def test_design_only_inputs_build_a_snapshot():
    inputs = build_rl_inputs(make_twin())
    snapshot = _build(inputs)

    assert snapshot.maps.station_ids == ("mixing", "forming", "baking", "packing")
    assert set(snapshot.maps.worker_ids) == {"wrk-01", "wrk-03", "wrk-05", "wrk-06", "wrk-07"}
    assert inputs["simulation_state"] is None
    assert snapshot.baselines.line_throughput == pytest.approx(60.0)


def test_stations_without_job_get_a_default_job():
    twin = make_twin()
    twin.job_desks = [job for job in twin.job_desks if job.stage_id != "packing"]
    inputs = build_rl_inputs(twin)
    jobs = {job["workflow_step"]: job["job_id"] for job in inputs["factory_md"]["job_descriptions"]}
    assert jobs["packing"] == "auto-packing"
    assert all("assigned_worker_names" not in job for job in inputs["factory_md"]["job_descriptions"])


def test_incomplete_evaluations_are_dropped_and_noise_defaulted():
    inputs = build_rl_inputs(make_twin())
    evaluations = inputs["init_state"]["llm_compatibility_and_evaluations"]
    assert [entry["job_id"] for entry in evaluations] == ["job-mixing"]
    mixing = inputs["factory_md"]["assets"][0]
    assert mixing["environmental_factors"]["noise_level_db"] == 60.0


def test_browser_run_feeds_simulation_state_from_working_snapshot():
    end = make_runtime("off_shift", 0.0)
    working = make_runtime("active", 0.8)
    inputs = build_rl_inputs(make_twin(), end_state=end, working_state=working)
    snapshot = _build(inputs)

    assignments = inputs["simulation_state"]["live_simulation_state"]["current_assignments"]
    rates = {entry["worker_id"]: entry["calculated_realtime_metrics"]["effective_throughput_per_hour"] for entry in assignments}
    assert "wrk-99" not in rates
    assert rates["wrk-05"] == pytest.approx(60.0 * 0.8)
    assert snapshot.baselines.line_throughput == pytest.approx(48.0)
    assert inputs["simulation_summary"]["system_bottlenecks"] == ["baking"]


def test_twin_without_stages_is_rejected():
    twin = make_twin()
    twin.process_stages = []
    with pytest.raises(RlInputError):
        build_rl_inputs(twin)
