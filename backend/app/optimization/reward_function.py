from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Optional

import numpy as np

EPSILON = 1e-6
COST_RATIO_CEILING = 2.0
OBJECTIVE_KEYS = ("throughput", "cost", "fatigue", "bottleneck")


@dataclass(frozen=True)
class RewardWeights:
    throughput: float = 0.40
    cost: float = 0.20
    fatigue: float = 0.25
    bottleneck: float = 0.15
    distress_threshold: float = 0.65
    distress_lambda: float = 4.0
    churn_penalty: float = 0.02
    violation_penalty: float = 0.05
    terminal_gain: float = 0.50
    terminal_burnout: float = 0.30
    terminal_capex: float = 0.20

    def objective_vector(self) -> np.ndarray:
        return np.array(
            [self.throughput, self.cost, self.fatigue, self.bottleneck],
            dtype=np.float32,
        )

    def normalized(self) -> "RewardWeights":
        vector = self.objective_vector()
        total = float(vector.sum())
        if total <= EPSILON:
            return self
        scaled = vector / total
        return replace(
            self,
            throughput=float(scaled[0]),
            cost=float(scaled[1]),
            fatigue=float(scaled[2]),
            bottleneck=float(scaled[3]),
        )

    def as_dict(self) -> dict[str, float]:
        return {key: float(getattr(self, key)) for key in OBJECTIVE_KEYS}

    @staticmethod
    def sample(
        rng: np.random.Generator,
        concentration: tuple[float, float, float, float] = (2.0, 1.5, 1.5, 1.0),
        template: Optional["RewardWeights"] = None,
    ) -> "RewardWeights":
        base = template if template is not None else RewardWeights()
        drawn = rng.dirichlet(np.asarray(concentration, dtype=np.float64))
        return replace(
            base,
            throughput=float(drawn[0]),
            cost=float(drawn[1]),
            fatigue=float(drawn[2]),
            bottleneck=float(drawn[3]),
        )

    @staticmethod
    def from_vector(
        vector: np.ndarray, template: Optional["RewardWeights"] = None
    ) -> "RewardWeights":
        base = template if template is not None else RewardWeights()
        return replace(
            base,
            throughput=float(vector[0]),
            cost=float(vector[1]),
            fatigue=float(vector[2]),
            bottleneck=float(vector[3]),
        ).normalized()


@dataclass(frozen=True)
class RewardBreakdown:
    total: float
    throughput_term: float
    cost_term: float
    fatigue_term: float
    bottleneck_term: float
    penalty_term: float
    line_throughput: float
    good_throughput: float
    error_rate: float
    cost_per_item: float
    mean_fatigue: float
    max_fatigue: float
    total_shortfall: float
    bottleneck_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "throughput_term": self.throughput_term,
            "cost_term": self.cost_term,
            "fatigue_term": self.fatigue_term,
            "bottleneck_term": self.bottleneck_term,
            "penalty_term": self.penalty_term,
            "line_throughput": self.line_throughput,
            "good_throughput": self.good_throughput,
            "error_rate": self.error_rate,
            "cost_per_item": self.cost_per_item,
            "mean_fatigue": self.mean_fatigue,
            "max_fatigue": self.max_fatigue,
            "total_shortfall": self.total_shortfall,
            "bottleneck_count": self.bottleneck_count,
        }


def line_throughput(station_potential: np.ndarray) -> float:
    if station_potential.size == 0:
        return 0.0
    return float(np.min(station_potential))


def composite_error_rate(station_error: np.ndarray) -> float:
    survival = float(np.prod(np.clip(1.0 - station_error, 0.0, 1.0)))
    return float(np.clip(1.0 - survival, 0.0, 1.0))


def good_throughput(station_potential: np.ndarray, station_error: np.ndarray) -> float:
    return line_throughput(station_potential) * (1.0 - composite_error_rate(station_error))


def cost_per_item(total_hourly_cost: float, good_units_per_hour: float) -> float:
    return float(total_hourly_cost / max(good_units_per_hour, EPSILON))


def throughput_term(good_units_per_hour: float, target_line_rate: float) -> float:
    return float(np.clip(good_units_per_hour / max(target_line_rate, EPSILON), 0.0, 1.0))


def cost_term(current_cost_per_item: float, baseline_cost_per_item: float) -> float:
    ratio = current_cost_per_item / max(baseline_cost_per_item, EPSILON)
    return float(np.clip(ratio, 0.0, COST_RATIO_CEILING) - 1.0)


def fatigue_term(
    fatigue: np.ndarray,
    active_mask: np.ndarray,
    distress_threshold: float,
    distress_lambda: float,
) -> float:
    selected = fatigue[active_mask]
    if selected.size == 0:
        return 0.0
    mean_load = float(np.mean(selected))
    excess = np.maximum(0.0, selected - distress_threshold)
    distress = float(np.mean(np.square(excess)))
    return mean_load + distress_lambda * distress


def bottleneck_term(station_potential: np.ndarray, target_line_rate: float) -> float:
    if station_potential.size == 0:
        return 0.0
    shortfall = np.maximum(0.0, target_line_rate - station_potential)
    return float(np.mean(shortfall / max(target_line_rate, EPSILON)))


def bottleneck_stations(
    station_potential: np.ndarray, target_line_rate: float, tolerance: float = 0.02
) -> np.ndarray:
    threshold = target_line_rate * (1.0 - tolerance)
    return np.flatnonzero(station_potential < threshold)


def compute_step_reward(
    station_potential: np.ndarray,
    station_error: np.ndarray,
    fatigue: np.ndarray,
    active_mask: np.ndarray,
    total_hourly_cost: float,
    target_line_rate: float,
    baseline_cost_per_item: float,
    weights: RewardWeights,
    reassigned: bool = False,
    violations: int = 0,
) -> RewardBreakdown:
    realized_line = line_throughput(station_potential)
    error_rate = composite_error_rate(station_error)
    good_units = realized_line * (1.0 - error_rate)

    unit_cost = cost_per_item(total_hourly_cost, good_units)

    term_throughput = throughput_term(good_units, target_line_rate)
    term_cost = cost_term(unit_cost, baseline_cost_per_item)
    term_fatigue = fatigue_term(
        fatigue, active_mask, weights.distress_threshold, weights.distress_lambda
    )
    term_bottleneck = bottleneck_term(station_potential, target_line_rate)

    penalty = weights.churn_penalty * float(reassigned)
    penalty += weights.violation_penalty * float(violations)

    total = weights.throughput * term_throughput
    total -= weights.cost * term_cost
    total -= weights.fatigue * term_fatigue
    total -= weights.bottleneck * term_bottleneck
    total -= penalty

    selected_fatigue = fatigue[active_mask]
    shortfall = np.maximum(0.0, target_line_rate - station_potential)

    return RewardBreakdown(
        total=float(total),
        throughput_term=float(term_throughput),
        cost_term=float(term_cost),
        fatigue_term=float(term_fatigue),
        bottleneck_term=float(term_bottleneck),
        penalty_term=float(penalty),
        line_throughput=float(realized_line),
        good_throughput=float(good_units),
        error_rate=float(error_rate),
        cost_per_item=float(unit_cost),
        mean_fatigue=float(np.mean(selected_fatigue)) if selected_fatigue.size else 0.0,
        max_fatigue=float(np.max(selected_fatigue)) if selected_fatigue.size else 0.0,
        total_shortfall=float(np.sum(shortfall) / max(target_line_rate, EPSILON)),
        bottleneck_count=int(bottleneck_stations(station_potential, target_line_rate).size),
    )


def compute_terminal_reward(
    final_throughput_ratio: float,
    initial_throughput_ratio: float,
    burnout_fraction: float,
    capex_ratio: float,
    weights: RewardWeights,
) -> float:
    gain = weights.terminal_gain * (final_throughput_ratio - initial_throughput_ratio)
    burnout = weights.terminal_burnout * float(np.clip(burnout_fraction, 0.0, 1.0))
    capex = weights.terminal_capex * float(np.clip(capex_ratio, 0.0, 1.0))
    return float(gain - burnout - capex)


def pareto_front(objectives: np.ndarray, maximize: np.ndarray) -> np.ndarray:
    oriented = objectives * np.where(maximize, 1.0, -1.0)
    count = oriented.shape[0]
    keep = np.ones(count, dtype=bool)

    for index in range(count):
        if not keep[index]:
            continue
        dominated = np.all(oriented >= oriented[index], axis=1)
        dominated &= np.any(oriented > oriented[index], axis=1)
        if np.any(dominated):
            keep[index] = False

    return np.flatnonzero(keep)