from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None

VIBRATION_SCALE = {"low": 0.0, "medium": 0.5, "high": 1.0}
DEMAND_SCALE = {"low": 0.0, "medium": 0.5, "high": 1.0}
SEVERITY_SCALE = {"low": 0.0, "moderate": 0.34, "high": 0.67, "critical": 1.0}
BURNOUT_SCALE = {"low": 0.0, "medium": 0.5, "high": 1.0}
STATUS_ORDER = ("processing", "waiting_on_machine", "idle_waiting_input", "on_break")

AGE_RANGE = (16.0, 75.0)
NOISE_RANGE = (30.0, 95.0)
EXPERIENCE_CAP = 40.0
HOURS_CAP = 12.0
SHIFT_CAP = 7.0
UNITS_CAP = 4.0

EVALUATION_FIELDS = (
    "overall_compatibility_score",
    "throughput_multiplier",
    "error_multiplier",
    "fatigue_accumulation_rate",
    "stress_sensitivity_factor",
)

EVALUATION_BOUNDS = {
    "overall_compatibility_score": (0.0, 1.0),
    "throughput_multiplier": (0.8, 1.2),
    "error_multiplier": (0.4, 1.5),
    "fatigue_accumulation_rate": (0.3, 1.5),
    "stress_sensitivity_factor": (0.4, 1.0),
}

WORKER_FEATURE_SCALARS = 12
STATION_FEATURE_SCALARS = 16
GLOBAL_FEATURE_COUNT = 20

BUNDLE_FILES = {
    "factory_md": "factory_md.json",
    "worker_md": "worker_md.json",
    "init_state": "init_state.json",
    "simulation_state": "simulation_state.json",
}


def scale(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return float(np.clip((value - low) / (high - low), 0.0, 1.0))


def normalize_evaluation(field_name: str, value: float) -> float:
    low, high = EVALUATION_BOUNDS[field_name]
    return scale(value, low, high)


def denormalize_evaluation(field_name: str, value: float) -> float:
    low, high = EVALUATION_BOUNDS[field_name]
    return float(low + value * (high - low))


@dataclass(frozen=True)
class IndexMaps:
    worker_ids: tuple[str, ...]
    worker_names: tuple[str, ...]
    station_ids: tuple[str, ...]
    asset_ids: tuple[str, ...]
    job_ids: tuple[str, ...]
    worker_row: dict[str, int]
    station_col: dict[str, int]

    @property
    def n_workers(self) -> int:
        return len(self.worker_ids)

    @property
    def n_stations(self) -> int:
        return len(self.station_ids)


@dataclass(frozen=True)
class Constraints:
    min_headcount: np.ndarray
    max_headcount: np.ndarray
    units_available: np.ndarray
    target_line_rate: float
    tick_minutes: int = 15
    shift_hours: float = 8.0

    @property
    def ticks_per_shift(self) -> int:
        return int(self.shift_hours * 60 / self.tick_minutes)


@dataclass(frozen=True)
class Baselines:
    cost_per_item: float
    good_throughput: float
    error_rate: float
    line_throughput: float


@dataclass
class EnvSnapshot:
    maps: IndexMaps
    worker_static: np.ndarray
    station_static: np.ndarray
    station_capacity: np.ndarray
    asset_cost_per_hour: np.ndarray
    compatibility: np.ndarray
    assignment: np.ndarray
    constraints: Constraints
    baselines: Baselines
    raw_assets: list[dict[str, Any]] = field(default_factory=list)
    raw_jobs: list[dict[str, Any]] = field(default_factory=list)
    raw_workers: list[dict[str, Any]] = field(default_factory=list)
    raw_flow: dict[str, Any] = field(default_factory=dict)

    @property
    def observation_dim(self) -> int:
        n, m = self.maps.n_workers, self.maps.n_stations
        worker_block = n * (WORKER_FEATURE_SCALARS + m + len(STATUS_ORDER))
        station_block = m * STATION_FEATURE_SCALARS
        compat_block = len(EVALUATION_FIELDS) * n * m
        return worker_block + station_block + compat_block + GLOBAL_FEATURE_COUNT

    @property
    def action_nvec(self) -> np.ndarray:
        n, m = self.maps.n_workers, self.maps.n_stations
        return np.array([(n + 1) * (m + 2), 2 * m + 1], dtype=np.int64)

    def summary(self) -> dict[str, Any]:
        return {
            "n_workers": self.maps.n_workers,
            "n_stations": self.maps.n_stations,
            "observation_dim": self.observation_dim,
            "assignment_actions": int(self.action_nvec[0]),
            "capital_actions": int(self.action_nvec[1]),
            "mask_bits": int(self.action_nvec.sum()),
            "target_line_rate": self.constraints.target_line_rate,
            "ticks_per_shift": self.constraints.ticks_per_shift,
            "baseline_throughput": self.baselines.good_throughput,
            "baseline_error_rate": self.baselines.error_rate,
            "baseline_cost_per_item": self.baselines.cost_per_item,
        }


def validate_payload(payload: dict[str, Any], schema_path: Path) -> None:
    if Draft202012Validator is None:
        return

    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.path))

    if errors:
        details = "; ".join(f"{list(error.path)}: {error.message}" for error in errors)
        raise ValueError(f"Skema {Path(schema_path).name} gagal divalidasi: {details}")


class SnapshotBuilder:
    def __init__(
        self,
        factory_md: dict[str, Any],
        worker_md: dict[str, Any] | list[dict[str, Any]],
        init_state: dict[str, Any],
        compatibility_records: Optional[list[dict[str, Any]]] = None,
        simulation_state: Optional[dict[str, Any]] = None,
        tick_minutes: int = 15,
        shift_hours: float = 8.0,
    ) -> None:
        self.factory = factory_md

        if isinstance(worker_md, dict):
            self.workers = worker_md.get("workers", [])
        else:
            self.workers = worker_md or []

        self.flow = init_state["factory_flow_rightnow"]

        if compatibility_records is not None:
            self.priors = compatibility_records
        else:
            self.priors = init_state.get("llm_compatibility_and_evaluations", [])

        if simulation_state and "live_simulation_state" in simulation_state:
            self.simulation = simulation_state["live_simulation_state"]
        else:
            self.simulation = simulation_state or None

        self.tick_minutes = tick_minutes
        self.shift_hours = shift_hours

    def build(self) -> EnvSnapshot:
        maps = self._build_maps()
        capacity, asset_cost = self._build_station_arrays(maps)
        constraints = self._build_constraints(maps, capacity)
        assignment = self._build_assignment(maps)
        worker_static = self._build_worker_static(maps, constraints)
        station_static = self._build_station_static(maps, constraints, capacity, asset_cost)
        compatibility = self._build_compatibility(maps)
        baselines = self._build_baselines(maps, constraints, asset_cost)

        return EnvSnapshot(
            maps=maps,
            worker_static=worker_static,
            station_static=station_static,
            station_capacity=capacity,
            asset_cost_per_hour=asset_cost,
            compatibility=compatibility,
            assignment=assignment,
            constraints=constraints,
            baselines=baselines,
            raw_assets=self.factory["assets"],
            raw_jobs=self.factory["job_descriptions"],
            raw_workers=self.workers,
            raw_flow=self.flow,
        )

    def _build_maps(self) -> IndexMaps:
        station_ids = tuple(self.factory["factory_info"]["workflow_sequence"])
        worker_ids = tuple(worker["worker_id"] for worker in self.workers)
        worker_names = tuple(worker["name"] for worker in self.workers)

        station_col = {key: index for index, key in enumerate(station_ids)}

        asset_ids = [""] * len(station_ids)
        for asset in self.factory["assets"]:
            asset_ids[station_col[asset["workflow_step"]]] = asset["asset_id"]

        job_ids = [""] * len(station_ids)
        for job in self.factory["job_descriptions"]:
            job_ids[station_col[job["workflow_step"]]] = job["job_id"]

        return IndexMaps(
            worker_ids=worker_ids,
            worker_names=worker_names,
            station_ids=station_ids,
            asset_ids=tuple(asset_ids),
            job_ids=tuple(job_ids),
            worker_row={key: index for index, key in enumerate(worker_ids)},
            station_col=station_col,
        )

    def _build_station_arrays(self, maps: IndexMaps) -> tuple[np.ndarray, np.ndarray]:
        capacity = np.zeros(maps.n_stations, dtype=np.float32)
        cost = np.zeros(maps.n_stations, dtype=np.float32)

        for asset in self.factory["assets"]:
            column = maps.station_col[asset["workflow_step"]]
            units = float(asset.get("units_available", 1))
            capacity[column] = float(asset["base_throughput_capacity"]) * max(units, 1.0)
            cost[column] = float(asset["operational_cost_per_hour"]) * max(units, 1.0)

        return capacity, cost

    def _build_constraints(self, maps: IndexMaps, capacity: np.ndarray) -> Constraints:
        units = np.ones(maps.n_stations, dtype=np.float32)
        for asset in self.factory["assets"]:
            column = maps.station_col[asset["workflow_step"]]
            units[column] = float(asset.get("units_available", 1))

        minimum = np.ones(maps.n_stations, dtype=np.int32)
        for job in self.factory["job_descriptions"]:
            column = maps.station_col[job["workflow_step"]]
            assigned = job.get("assigned_worker_name") or job.get("assigned_worker_names") or []
            minimum[column] = max(1, len(assigned))

        maximum = np.maximum(minimum, units.astype(np.int32)) + 1

        return Constraints(
            min_headcount=minimum,
            max_headcount=maximum,
            units_available=units,
            target_line_rate=float(np.min(capacity[capacity > 0])) if np.any(capacity > 0) else 1.0,
            tick_minutes=self.tick_minutes,
            shift_hours=self.shift_hours,
        )

    def _build_assignment(self, maps: IndexMaps) -> np.ndarray:
        assignment = np.full(maps.n_workers, -1, dtype=np.int32)
        for position in self.flow["staff_current_positions"]:
            row = maps.worker_row.get(position["worker_id"])
            if row is None:
                continue
            assignment[row] = maps.station_col[position["current_stage_id"]]
        return assignment

    def _metrics_by_worker(self) -> dict[str, dict[str, Any]]:
        if not self.simulation:
            return {}
        assignments = self.simulation.get("current_assignments", [])
        return {entry["worker_id"]: entry["calculated_realtime_metrics"] for entry in assignments}

    def _build_worker_static(self, maps: IndexMaps, constraints: Constraints) -> np.ndarray:
        width = WORKER_FEATURE_SCALARS + maps.n_stations + len(STATUS_ORDER)
        matrix = np.zeros((maps.n_workers, width), dtype=np.float32)
        metrics = self._metrics_by_worker()
        statuses = {
            position["worker_id"]: position["activity_status"]
            for position in self.flow["staff_current_positions"]
        }

        for worker in self.workers:
            row = maps.worker_row[worker["worker_id"]]
            demographics = worker["demographics"]
            shift = worker["shift_context"]
            realtime = metrics.get(worker["worker_id"], {})

            matrix[row, 0] = scale(demographics["age"], *AGE_RANGE)
            matrix[row, 1] = scale(demographics["years_of_experience"], 0.0, EXPERIENCE_CAP)
            matrix[row, 2] = demographics["baseline_physical_stamina"]
            matrix[row, 3] = demographics["cognitive_resilience"]
            matrix[row, 4] = scale(shift["hours_worked_today"], 0.0, HOURS_CAP)
            matrix[row, 5] = scale(shift["consecutive_shifts"], 0.0, SHIFT_CAP)
            matrix[row, 6] = realtime.get("current_fatigue_level", 0.0)
            matrix[row, 7] = realtime.get("current_stress_level", 0.0)
            matrix[row, 8] = min(1.0, realtime.get("effective_error_probability", 0.0) * 10.0)
            matrix[row, 9] = BURNOUT_SCALE.get(realtime.get("burnout_hazard_risk", "low"), 0.0)
            matrix[row, 10] = scale(
                realtime.get("effective_throughput_per_hour", 0.0),
                0.0,
                constraints.target_line_rate,
            )
            matrix[row, 11] = 0.0

            station_offset = WORKER_FEATURE_SCALARS
            column = self._current_station_column(maps, worker["worker_id"])
            if column >= 0:
                matrix[row, station_offset + column] = 1.0

            status_offset = station_offset + maps.n_stations
            status = statuses.get(worker["worker_id"], "processing")
            matrix[row, status_offset + STATUS_ORDER.index(status)] = 1.0

        return matrix

    def _current_station_column(self, maps: IndexMaps, worker_id: str) -> int:
        for position in self.flow["staff_current_positions"]:
            if position["worker_id"] == worker_id:
                return maps.station_col[position["current_stage_id"]]
        return -1

    def _build_station_static(
        self,
        maps: IndexMaps,
        constraints: Constraints,
        capacity: np.ndarray,
        asset_cost: np.ndarray,
    ) -> np.ndarray:
        matrix = np.zeros((maps.n_stations, STATION_FEATURE_SCALARS), dtype=np.float32)
        max_cost = float(np.max(asset_cost)) if np.any(asset_cost) else 1.0
        capacity_reference = max(float(np.max(capacity)), 1.0)
        jobs = {job["workflow_step"]: job for job in self.factory["job_descriptions"]}

        for asset in self.factory["assets"]:
            column = maps.station_col[asset["workflow_step"]]
            environment = asset["environmental_factors"]
            demands = jobs[asset["workflow_step"]]["demands"]

            matrix[column, 0] = float(asset["is_automated"])
            matrix[column, 1] = scale(capacity[column], 0.0, capacity_reference)
            matrix[column, 2] = scale(asset.get("units_available", 1), 0.0, UNITS_CAP)
            matrix[column, 3] = scale(asset_cost[column], 0.0, max_cost)
            matrix[column, 4] = scale(environment["noise_level_db"], *NOISE_RANGE)
            matrix[column, 5] = VIBRATION_SCALE[environment["vibration_hazard_level"]]
            matrix[column, 6] = environment["physical_strain_index"]
            matrix[column, 7] = demands["required_cognitive_focus"]
            matrix[column, 8] = DEMAND_SCALE[demands["physical_demand_level"]]
            matrix[column, 9] = demands["task_complexity"]
            matrix[column, 10] = SEVERITY_SCALE[demands["error_severity"]]

        return matrix

    def _build_compatibility(self, maps: IndexMaps) -> np.ndarray:
        tensor = np.zeros(
            (maps.n_workers, maps.n_stations, len(EVALUATION_FIELDS)), dtype=np.float32
        )
        observed: set[tuple[int, int]] = set()

        job_station = {
            job["job_id"]: maps.station_col[job["workflow_step"]]
            for job in self.factory["job_descriptions"]
        }

        for prior in self.priors:
            row = maps.worker_row.get(prior["worker_id"])
            column = job_station.get(prior["job_id"])
            if row is None or column is None:
                continue
            for index, field_name in enumerate(EVALUATION_FIELDS):
                tensor[row, column, index] = normalize_evaluation(
                    field_name, prior["evaluations"][field_name]
                )
            observed.add((row, column))

        for row in range(maps.n_workers):
            for column in range(maps.n_stations):
                if (row, column) not in observed:
                    tensor[row, column] = self._heuristic_pair(maps, row, column)

        return tensor

    def _heuristic_pair(self, maps: IndexMaps, row: int, column: int) -> np.ndarray:
        worker = self.workers[row]
        demographics = worker["demographics"]
        station_id = maps.station_ids[column]

        job = next(item for item in self.factory["job_descriptions"] if item["workflow_step"] == station_id)
        asset = next(item for item in self.factory["assets"] if item["workflow_step"] == station_id)

        focus_gap = abs(
            demographics["cognitive_resilience"] - job["demands"]["required_cognitive_focus"]
        )
        physical_gap = max(
            0.0,
            DEMAND_SCALE[job["demands"]["physical_demand_level"]]
            - demographics["baseline_physical_stamina"],
        )
        strain = asset["environmental_factors"]["physical_strain_index"]

        fit = float(np.clip(0.5 * (1.0 - focus_gap) + 0.5 * (1.0 - physical_gap), 0.0, 1.0))

        raw = {
            "overall_compatibility_score": fit,
            "throughput_multiplier": 0.8 + 0.4 * fit,
            "error_multiplier": 1.5 - 1.1 * fit,
            "fatigue_accumulation_rate": 0.3
            + 1.2 * strain * (1.0 - demographics["baseline_physical_stamina"]),
            "stress_sensitivity_factor": 0.4 + 0.6 * (1.0 - demographics["cognitive_resilience"]),
        }

        return np.array(
            [normalize_evaluation(name, raw[name]) for name in EVALUATION_FIELDS],
            dtype=np.float32,
        )

    def _build_baselines(
        self, maps: IndexMaps, constraints: Constraints, asset_cost: np.ndarray
    ) -> Baselines:
        metrics = self._metrics_by_worker()
        throughputs = [entry.get("effective_throughput_per_hour", 0.0) for entry in metrics.values()]
        errors = [entry.get("effective_error_probability", 0.0) for entry in metrics.values()]

        line = min(throughputs) if throughputs else constraints.target_line_rate
        survival = float(np.prod([1.0 - value for value in errors])) if errors else 1.0
        error_rate = 1.0 - survival
        good = line * survival

        hourly_cost = float(np.sum(asset_cost))
        return Baselines(
            cost_per_item=hourly_cost / max(good, 1e-6),
            good_throughput=good,
            error_rate=error_rate,
            line_throughput=line,
        )


def build_snapshot(
    factory_md: dict[str, Any],
    worker_md: dict[str, Any],
    init_state: dict[str, Any],
    simulation_state: Optional[dict[str, Any]] = None,
) -> EnvSnapshot:
    builder = SnapshotBuilder(
        factory_md=factory_md,
        worker_md=worker_md,
        init_state=init_state,
        simulation_state=simulation_state,
    )
    return builder.build()


def load_bundle(directory: str | Path) -> EnvSnapshot:
    base = Path(directory)
    payloads = {}

    for key, filename in BUNDLE_FILES.items():
        path = base / filename
        payloads[key] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    missing = [key for key in ("factory_md", "worker_md", "init_state") if payloads[key] is None]
    if missing:
        raise FileNotFoundError(f"Bundle {base} tidak lengkap, hilang: {missing}")

    return build_snapshot(
        factory_md=payloads["factory_md"],
        worker_md=payloads["worker_md"],
        init_state=payloads["init_state"],
        simulation_state=payloads["simulation_state"],
    )


def load_corpus(manifest_path: str | Path) -> list[EnvSnapshot]:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    base = Path(manifest_path).parent
    return [load_bundle(base / entry["directory"]) for entry in manifest["bundles"]]