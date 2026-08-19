from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from backend.app.optimization.reward_function import (
    RewardBreakdown,
    RewardWeights,
    bottleneck_stations,
    compute_step_reward,
    compute_terminal_reward,
    throughput_term,
)
from backend.app.services.snapshot_builder import (
    EVALUATION_BOUNDS,
    EVALUATION_FIELDS,
    GLOBAL_FEATURE_COUNT,
    STATION_FEATURE_SCALARS,
    STATUS_ORDER,
    WORKER_FEATURE_SCALARS,
    EnvSnapshot,
)

EPSILON = 1e-6
STANDBY = -1

COLUMN_FATIGUE = 6
COLUMN_STRESS = 7
COLUMN_ERROR = 8
COLUMN_BURNOUT = 9
COLUMN_THROUGHPUT = 10
COLUMN_TENURE = 11

STATION_COLUMN_AUTOMATED = 0
STATION_COLUMN_CAPACITY = 1
STATION_COLUMN_HEADCOUNT = 11
STATION_COLUMN_WIP = 12
STATION_COLUMN_THROUGHPUT = 13
STATION_COLUMN_SHORTFALL = 14
STATION_COLUMN_UTILIZATION = 15


@dataclass(frozen=True)
class HumanFactorsParams:
    fatigue_gain: float = 0.55
    fatigue_recovery: float = 0.35
    stress_tau_hours: float = 0.75
    stress_optimum: float = 0.40
    stress_spread: float = 0.28
    minimum_performance: float = 0.25
    fatigue_throughput_beta: float = 0.45
    fatigue_error_gamma: float = 1.80
    base_error_probability: float = 0.012
    wip_capacity: float = 400.0
    automation_throughput_gain: float = 1.25
    automation_error_factor: float = 0.25
    burnout_threshold: float = 0.65
    break_ticks: int = 2
    rotation_cooldown_ticks: int = 2
    rotation_budget: int = 8
    hire_capex: float = 50_000_000.0
    automation_capex: float = 70_000_000.0
    worker_wage_per_hour: float = 25_000.0
    randomize_sigma: float = 0.15


@dataclass(frozen=True)
class ScenarioConstraints:
    hiring_allowed: bool = False
    automation_allowed: bool = False
    mutation_allowed: bool = False
    capex_budget: float = 0.0
    hire_slots: int = 0


def denormalize_evaluation(field_index: int, value: float) -> float:
    low, high = EVALUATION_BOUNDS[EVALUATION_FIELDS[field_index]]
    return float(low + value * (high - low))


class FactoryOptimizationEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(
        self,
        snapshot: EnvSnapshot,
        scenario: Optional[ScenarioConstraints] = None,
        params: Optional[HumanFactorsParams] = None,
        weight_template: Optional[RewardWeights] = None,
        sample_weights: bool = True,
        randomize_start: bool = True,
        seed: Optional[int] = None,
    ) -> None:
        super().__init__()

        self.snapshot = snapshot
        self.scenario = scenario if scenario is not None else ScenarioConstraints()
        self.params = params if params is not None else HumanFactorsParams()
        self.weight_template = weight_template if weight_template is not None else RewardWeights()
        self.sample_weights = sample_weights
        self.randomize_start = randomize_start

        self.rng = np.random.default_rng(seed)

        self.n_base_workers = snapshot.maps.n_workers
        self.n_stations = snapshot.maps.n_stations
        self.n_workers = self.n_base_workers + self.scenario.hire_slots

        self.horizon = snapshot.constraints.ticks_per_shift
        self.dt_hours = snapshot.constraints.tick_minutes / 60.0
        self.target_rate = float(snapshot.constraints.target_line_rate)

        self._extend_static_arrays()
        self._prepare_station_constants()

        self.worker_block_width = WORKER_FEATURE_SCALARS + self.n_stations + len(STATUS_ORDER)
        self.observation_dim = (
            self.n_workers * self.worker_block_width
            + self.n_stations * STATION_FEATURE_SCALARS
            + len(EVALUATION_FIELDS) * self.n_workers * self.n_stations
            + GLOBAL_FEATURE_COUNT
        )

        self.assignment_actions = (self.n_workers + 1) * (self.n_stations + 2)
        self.capital_actions = 2 * self.n_stations + 1

        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(self.observation_dim,), dtype=np.float32
        )
        self.action_space = spaces.MultiDiscrete(
            [self.assignment_actions, self.capital_actions]
        )

        self.weights = self.weight_template
        self._initial_throughput_ratio = 0.0

    def _extend_static_arrays(self) -> None:
        base_worker = self.snapshot.worker_static
        base_compat = self.snapshot.compatibility

        if self.scenario.hire_slots == 0:
            self.worker_static_base = base_worker.copy()
            self.compatibility_base = base_compat.copy()
            self.base_active = np.ones(self.n_workers, dtype=bool)
            return

        median_worker = np.median(base_worker, axis=0)
        median_worker[WORKER_FEATURE_SCALARS:] = 0.0
        median_worker[COLUMN_FATIGUE] = 0.0
        median_worker[COLUMN_STRESS] = 0.0
        median_worker[COLUMN_ERROR] = 0.0
        median_worker[COLUMN_BURNOUT] = 0.0
        median_worker[COLUMN_THROUGHPUT] = 0.0
        median_worker[COLUMN_TENURE] = 0.0

        extra_workers = np.tile(median_worker, (self.scenario.hire_slots, 1))
        self.worker_static_base = np.vstack([base_worker, extra_workers]).astype(np.float32)

        median_compat = np.median(base_compat, axis=0, keepdims=True)
        extra_compat = np.tile(median_compat, (self.scenario.hire_slots, 1, 1))
        self.compatibility_base = np.concatenate([base_compat, extra_compat], axis=0)

        self.base_active = np.zeros(self.n_workers, dtype=bool)
        self.base_active[: self.n_base_workers] = True

    def _prepare_station_constants(self) -> None:
        station_static = self.snapshot.station_static
        constraints = self.snapshot.constraints

        self.station_static_base = station_static.copy()
        self.units = constraints.units_available.astype(np.float32)
        self.min_headcount = constraints.min_headcount.astype(np.int32)
        self.max_headcount = np.maximum(constraints.max_headcount, 1).astype(np.int32)

        self.raw_capacity = self.snapshot.station_capacity.astype(np.float32).copy()
        self.asset_cost_absolute = self.snapshot.asset_cost_per_hour.astype(np.float32).copy()

        self.strain = station_static[:, 6].astype(np.float32)
        self.required_focus = station_static[:, 7].astype(np.float32)
        self.severity = station_static[:, 10].astype(np.float32)
        self.initial_automated = station_static[:, STATION_COLUMN_AUTOMATED] > 0.5

    def _stamina(self) -> np.ndarray:
        return np.maximum(self.worker_static_base[:, 2], 0.2)

    def _resilience(self) -> np.ndarray:
        return np.maximum(self.worker_static_base[:, 3], 0.2)

    def reset(
        self, *, seed: Optional[int] = None, options: Optional[dict[str, Any]] = None
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        if seed is not None:
            self.rng = np.random.default_rng(seed)

        if self.sample_weights:
            self.weights = RewardWeights.sample(self.rng, template=self.weight_template)
        elif options is not None and "weights" in options:
            self.weights = options["weights"]
        else:
            self.weights = self.weight_template.normalized()

        self.worker_state = self.worker_static_base.copy()
        self.station_state = self.station_static_base.copy()
        self.compatibility = self.compatibility_base.copy()

        self.active = self.base_active.copy()
        self.assignment = np.full(self.n_workers, STANDBY, dtype=np.int32)
        self.assignment[: self.n_base_workers] = self.snapshot.assignment

        self.fatigue = self.worker_state[:, COLUMN_FATIGUE].astype(np.float32).copy()
        self.stress = self.worker_state[:, COLUMN_STRESS].astype(np.float32).copy()

        if self.randomize_start:
            self._randomize_initial_condition()

        self.break_remaining = np.zeros(self.n_workers, dtype=np.int32)
        self.cooldown = np.zeros(self.n_workers, dtype=np.int32)
        self.tenure = np.zeros(self.n_workers, dtype=np.int32)

        self.automated = self.initial_automated.copy()
        self.wip = np.zeros(self.n_stations, dtype=np.float32)
        self.capex_spent = 0.0
        self.rotation_left = self.params.rotation_budget
        self.tick = 0

        self.moves_log: list[dict[str, Any]] = []
        self.upgrades_log: list[dict[str, Any]] = []
        self.hires_log: list[dict[str, Any]] = []
        self.initial_assignment = self.assignment.copy()

        potential, errors = self._evaluate_line()
        self._advance_wip(potential)
        self._initial_throughput_ratio = throughput_term(
            float(np.min(potential)) * float(np.prod(1.0 - errors)), self.target_rate
        )
        self.last_breakdown: Optional[RewardBreakdown] = None

        observation = self._build_observation(potential, errors)
        return observation, self._info(potential, errors)

    def _randomize_initial_condition(self) -> None:
        sigma = self.params.randomize_sigma
        noise = self.rng.normal(0.0, sigma, size=(self.n_workers, 4))

        self.worker_state[:, 4] = np.clip(self.worker_state[:, 4] + noise[:, 0], 0.0, 1.0)
        self.worker_state[:, 5] = np.clip(self.worker_state[:, 5] + noise[:, 1], 0.0, 1.0)
        self.fatigue = np.clip(self.fatigue + noise[:, 2], 0.0, 1.0).astype(np.float32)
        self.stress = np.clip(self.stress + noise[:, 3], 0.0, 1.0).astype(np.float32)

    def _worker_performance(self) -> np.ndarray:
        offset = self.stress - self.params.stress_optimum
        curve = np.exp(-np.square(offset) / (2.0 * self.params.stress_spread ** 2))
        floor = self.params.minimum_performance
        return floor + (1.0 - floor) * curve

    def _evaluate_line(self) -> tuple[np.ndarray, np.ndarray]:
        potential = np.zeros(self.n_stations, dtype=np.float32)
        errors = np.zeros(self.n_stations, dtype=np.float32)
        performance = self._worker_performance()

        self.worker_rate = np.zeros(self.n_workers, dtype=np.float32)
        self.worker_error = np.zeros(self.n_workers, dtype=np.float32)

        for station in range(self.n_stations):
            members = np.flatnonzero(
                (self.assignment == station) & self.active & (self.break_remaining == 0)
            )
            capacity = self.raw_capacity[station]
            if self.automated[station]:
                capacity *= self.params.automation_throughput_gain

            if members.size == 0:
                if self.automated[station]:
                    potential[station] = capacity
                    errors[station] = (
                        self.params.base_error_probability * self.params.automation_error_factor
                    )
                continue

            share = capacity / max(float(self.max_headcount[station]), 1.0)
            total_rate = 0.0
            error_values = []

            for worker in members:
                multiplier = denormalize_evaluation(1, self.compatibility[worker, station, 1])
                error_multiplier = denormalize_evaluation(2, self.compatibility[worker, station, 2])

                fatigue_factor = 1.0 - self.params.fatigue_throughput_beta * self.fatigue[worker]
                rate = share * multiplier * max(fatigue_factor, 0.1) * performance[worker]

                severity_scale = 1.0 + self.severity[station]
                error = self.params.base_error_probability * error_multiplier * severity_scale
                error *= 1.0 + self.params.fatigue_error_gamma * self.fatigue[worker]
                error /= max(performance[worker], self.params.minimum_performance)

                if self.automated[station]:
                    error *= self.params.automation_error_factor

                self.worker_rate[worker] = rate
                self.worker_error[worker] = float(np.clip(error, 0.0, 1.0))

                total_rate += rate
                error_values.append(self.worker_error[worker])

            potential[station] = min(capacity, total_rate)
            errors[station] = float(np.mean(error_values))

        return potential, errors

    def _advance_wip(self, potential: np.ndarray) -> None:
        upstream = np.inf
        for station in range(self.n_stations):
            available = self.wip[station] + (
                potential[station] * self.dt_hours if station == 0 else upstream
            )
            produced = min(potential[station] * self.dt_hours, available)
            self.wip[station] = max(0.0, available - produced)
            upstream = produced

    def _advance_human_factors(self) -> None:
        stamina = self._stamina()
        resilience = self._resilience()
        pressure = np.clip(self.wip / self.params.wip_capacity, 0.0, 1.0)

        for worker in range(self.n_workers):
            if not self.active[worker]:
                continue

            station = self.assignment[worker]
            resting = self.break_remaining[worker] > 0 or station == STANDBY

            if resting:
                self.fatigue[worker] -= self.dt_hours * self.params.fatigue_recovery
                target_stress = 0.1
            else:
                rate = denormalize_evaluation(3, self.compatibility[worker, station, 3])
                load = self.params.fatigue_gain * self.strain[station] * rate
                self.fatigue[worker] += self.dt_hours * load / stamina[worker]

                sensitivity = denormalize_evaluation(4, self.compatibility[worker, station, 4])
                focus_gap = max(0.0, float(self.required_focus[station]) - resilience[worker])
                target_stress = 0.20 + 0.45 * float(pressure[station])
                target_stress += 0.35 * focus_gap + 0.20 * float(self.strain[station])
                target_stress *= sensitivity

            self.fatigue[worker] = float(np.clip(self.fatigue[worker], 0.0, 1.0))
            decay = self.dt_hours / self.params.stress_tau_hours
            self.stress[worker] += (float(np.clip(target_stress, 0.0, 1.0)) - self.stress[worker]) * decay
            self.stress[worker] = float(np.clip(self.stress[worker], 0.0, 1.0))

    def _headcount(self) -> np.ndarray:
        counts = np.zeros(self.n_stations, dtype=np.int32)
        for station in range(self.n_stations):
            counts[station] = int(
                np.sum((self.assignment == station) & self.active & (self.break_remaining == 0))
            )
        return counts

    def _hourly_cost(self) -> float:
        counts = self._headcount()
        active_assets = (counts > 0) | self.automated
        asset_cost = float(np.sum(self.asset_cost_absolute * active_assets))
        working = int(np.sum(self.active & (self.assignment != STANDBY) & (self.break_remaining == 0)))
        return asset_cost + working * self.params.worker_wage_per_hour

    def decode_assignment(self, action: int) -> tuple[int, int]:
        span = self.n_stations + 2
        return int(action) // span, int(action) % span

    def action_masks(self) -> np.ndarray:
        assignment_mask = np.zeros(self.assignment_actions, dtype=bool)
        capital_mask = np.zeros(self.capital_actions, dtype=bool)

        span = self.n_stations + 2
        counts = self._headcount()

        assignment_mask[self.n_workers * span] = True

        if self.rotation_left > 0:
            for worker in range(self.n_workers):
                if not self.active[worker]:
                    continue
                if self.cooldown[worker] > 0 or self.break_remaining[worker] > 0:
                    continue

                origin = self.assignment[worker]
                releasable = origin == STANDBY or counts[origin] - 1 >= self.min_headcount[origin]

                for target in range(self.n_stations):
                    if target == origin:
                        continue
                    if counts[target] >= self.max_headcount[target]:
                        continue
                    if not releasable:
                        continue
                    assignment_mask[worker * span + target] = True

                if origin != STANDBY and releasable:
                    assignment_mask[worker * span + self.n_stations] = True
                    if self.scenario.mutation_allowed:
                        assignment_mask[worker * span + self.n_stations + 1] = True

        capital_mask[0] = True
        remaining = self.scenario.capex_budget - self.capex_spent

        if self.scenario.automation_allowed:
            for station in range(self.n_stations):
                if self.automated[station]:
                    continue
                if remaining >= self.params.automation_capex:
                    capital_mask[1 + station] = True

        if self.scenario.hiring_allowed and np.any(~self.active):
            for station in range(self.n_stations):
                if counts[station] >= self.max_headcount[station]:
                    continue
                if remaining >= self.params.hire_capex:
                    capital_mask[1 + self.n_stations + station] = True

        return np.concatenate([assignment_mask, capital_mask])

    def _apply_assignment(self, action: int) -> bool:
        worker, target = self.decode_assignment(action)
        if worker >= self.n_workers:
            return False

        origin = int(self.assignment[worker])

        if target < self.n_stations:
            self.assignment[worker] = target
            self.tenure[worker] = 0
            self.cooldown[worker] = self.params.rotation_cooldown_ticks
        elif target == self.n_stations:
            self.break_remaining[worker] = self.params.break_ticks
        else:
            self.assignment[worker] = STANDBY

        self.rotation_left = max(0, self.rotation_left - 1)
        self.moves_log.append(
            {
                "tick": self.tick,
                "worker_index": int(worker),
                "from_station": origin,
                "to_station": int(self.assignment[worker]),
                "on_break": bool(target == self.n_stations),
            }
        )
        return True

    def _apply_capital(self, action: int) -> None:
        if action == 0:
            return

        if 1 <= action <= self.n_stations:
            station = action - 1
            self.automated[station] = True
            self.min_headcount[station] = 0
            self.capex_spent += self.params.automation_capex
            self.upgrades_log.append({"tick": self.tick, "station_index": int(station)})
            return

        station = action - self.n_stations - 1
        candidates = np.flatnonzero(~self.active)
        if candidates.size == 0:
            return

        worker = int(candidates[0])
        self.active[worker] = True
        self.assignment[worker] = station
        self.capex_spent += self.params.hire_capex
        self.hires_log.append(
            {"tick": self.tick, "worker_index": worker, "station_index": int(station)}
        )

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        assignment_action = int(action[0])
        capital_action = int(action[1])

        reassigned = self._apply_assignment(assignment_action)
        self._apply_capital(capital_action)

        potential, errors = self._evaluate_line()
        self._advance_wip(potential)
        self._advance_human_factors()

        self.break_remaining = np.maximum(0, self.break_remaining - 1)
        self.cooldown = np.maximum(0, self.cooldown - 1)
        self.tenure = np.where(self.assignment >= 0, self.tenure + 1, 0)
        self.tick += 1

        breakdown = compute_step_reward(
            station_potential=potential,
            station_error=errors,
            fatigue=self.fatigue,
            active_mask=self.active,
            total_hourly_cost=self._hourly_cost(),
            target_line_rate=self.target_rate,
            baseline_cost_per_item=self.snapshot.baselines.cost_per_item,
            weights=self.weights,
            reassigned=reassigned,
            violations=0,
        )

        reward = breakdown.total
        terminated = self.tick >= self.horizon

        if terminated:
            burnout_fraction = float(
                np.mean(self.fatigue[self.active] >= self.params.burnout_threshold)
            )
            capex_ratio = self.capex_spent / max(self.scenario.capex_budget, EPSILON)
            reward += compute_terminal_reward(
                final_throughput_ratio=breakdown.throughput_term,
                initial_throughput_ratio=self._initial_throughput_ratio,
                burnout_fraction=burnout_fraction,
                capex_ratio=capex_ratio if self.scenario.capex_budget > 0 else 0.0,
                weights=self.weights,
            )

        self.last_breakdown = breakdown
        observation = self._build_observation(potential, errors)
        return observation, float(reward), bool(terminated), False, self._info(potential, errors)

    def _build_observation(self, potential: np.ndarray, errors: np.ndarray) -> np.ndarray:
        counts = self._headcount()

        self.worker_state[:, COLUMN_FATIGUE] = self.fatigue
        self.worker_state[:, COLUMN_STRESS] = self.stress
        self.worker_state[:, COLUMN_ERROR] = np.clip(self.worker_error * 10.0, 0.0, 1.0)
        self.worker_state[:, COLUMN_BURNOUT] = np.clip(
            (self.fatigue - 0.35) / 0.45, 0.0, 1.0
        )
        self.worker_state[:, COLUMN_THROUGHPUT] = np.clip(
            self.worker_rate / max(self.target_rate, EPSILON), 0.0, 1.0
        )
        self.worker_state[:, COLUMN_TENURE] = np.clip(
            self.tenure / max(self.horizon, 1), 0.0, 1.0
        )

        station_offset = WORKER_FEATURE_SCALARS
        status_offset = station_offset + self.n_stations
        self.worker_state[:, station_offset:] = 0.0

        for worker in range(self.n_workers):
            if not self.active[worker]:
                self.worker_state[worker, status_offset + 2] = 1.0
                continue

            station = int(self.assignment[worker])
            if station >= 0:
                self.worker_state[worker, station_offset + station] = 1.0

            if self.break_remaining[worker] > 0:
                status = "on_break"
            elif station == STANDBY:
                status = "idle_waiting_input"
            elif self.wip[station] > self.params.wip_capacity * 0.5:
                status = "waiting_on_machine"
            else:
                status = "processing"

            self.worker_state[worker, status_offset + STATUS_ORDER.index(status)] = 1.0

        self.station_state[:, STATION_COLUMN_AUTOMATED] = self.automated.astype(np.float32)
        self.station_state[:, STATION_COLUMN_HEADCOUNT] = counts / np.maximum(
            self.max_headcount, 1
        )
        self.station_state[:, STATION_COLUMN_WIP] = np.clip(
            self.wip / self.params.wip_capacity, 0.0, 1.0
        )
        self.station_state[:, STATION_COLUMN_THROUGHPUT] = np.clip(
            potential / max(self.target_rate, EPSILON), 0.0, 1.0
        )
        self.station_state[:, STATION_COLUMN_SHORTFALL] = np.clip(
            np.maximum(0.0, self.target_rate - potential) / max(self.target_rate, EPSILON), 0.0, 1.0
        )
        self.station_state[:, STATION_COLUMN_UTILIZATION] = np.clip(
            potential / np.maximum(self.raw_capacity, EPSILON), 0.0, 1.0
        )

        globals_block = self._global_features(potential, errors)

        return np.concatenate(
            [
                self.worker_state.reshape(-1),
                self.station_state.reshape(-1),
                self.compatibility.reshape(-1),
                globals_block,
            ]
        ).astype(np.float32)

    def _global_features(self, potential: np.ndarray, errors: np.ndarray) -> np.ndarray:
        line = float(np.min(potential)) if potential.size else 0.0
        survival = float(np.prod(np.clip(1.0 - errors, 0.0, 1.0)))
        good = line * survival
        cost = self._hourly_cost() / max(good, EPSILON)
        active_fatigue = self.fatigue[self.active]
        active_stress = self.stress[self.active]

        features = np.array(
            [
                self.tick / max(self.horizon, 1),
                np.clip(line / max(self.target_rate, EPSILON), 0.0, 1.0),
                survival,
                np.clip(cost / max(self.snapshot.baselines.cost_per_item, EPSILON) / 2.0, 0.0, 1.0),
                bottleneck_stations(potential, self.target_rate).size / max(self.n_stations, 1),
                np.clip(
                    np.sum(np.maximum(0.0, self.target_rate - potential))
                    / max(self.target_rate * self.n_stations, EPSILON),
                    0.0,
                    1.0,
                ),
                float(np.mean(active_fatigue)) if active_fatigue.size else 0.0,
                float(np.max(active_fatigue)) if active_fatigue.size else 0.0,
                float(np.mean(active_stress)) if active_stress.size else 0.0,
                float(np.max(active_stress)) if active_stress.size else 0.0,
                float(np.mean(self.break_remaining > 0)),
                np.clip(self.capex_spent / max(self.scenario.capex_budget, EPSILON), 0.0, 1.0)
                if self.scenario.capex_budget > 0
                else 0.0,
                float(self.scenario.hiring_allowed),
                float(self.scenario.automation_allowed),
                float(self.scenario.mutation_allowed),
                self.rotation_left / max(self.params.rotation_budget, 1),
                self.weights.throughput,
                self.weights.cost,
                self.weights.fatigue,
                self.weights.bottleneck,
            ],
            dtype=np.float32,
        )
        return np.clip(features, 0.0, 1.0)

    def _info(self, potential: np.ndarray, errors: np.ndarray) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "assignment": self.assignment.copy(),
            "initial_assignment": self.initial_assignment.copy(),
            "active": self.active.copy(),
            "automated": self.automated.copy(),
            "fatigue": self.fatigue.copy(),
            "stress": self.stress.copy(),
            "station_potential": potential.copy(),
            "station_error": errors.copy(),
            "capex_spent": self.capex_spent,
            "weights": self.weights,
            "moves": list(self.moves_log),
            "upgrades": list(self.upgrades_log),
            "hires": list(self.hires_log),
            "breakdown": self.last_breakdown.as_dict() if self.last_breakdown else None,
        }

    def close(self) -> None:
        return None