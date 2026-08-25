from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Optional

import numpy as np
import torch
import torch.nn as nn
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.callbacks import MaskableEvalCallback
from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy
from sb3_contrib.common.wrappers import ActionMasker
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.utils import set_random_seed
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecNormalize

from backend.app.optimization.factory_env import (
    FactoryOptimizationEnv,
    HumanFactorsParams,
    ScenarioConstraints,
)
from backend.app.optimization.reward_function import RewardWeights, pareto_front
from backend.app.services.snapshot_builder import SnapshotBuilder

SCENARIO_ORDER = ("scenario_01", "scenario_02", "scenario_03")

SCENARIO_LIBRARY = {
    "scenario_01": ScenarioConstraints(
        hiring_allowed=False,
        automation_allowed=False,
        mutation_allowed=False,
        capex_budget=0.0,
        hire_slots=0,
    ),
    "scenario_02": ScenarioConstraints(
        hiring_allowed=False,
        automation_allowed=True,
        mutation_allowed=True,
        capex_budget=70_000_000.0,
        hire_slots=0,
    ),
    "scenario_03": ScenarioConstraints(
        hiring_allowed=True,
        automation_allowed=True,
        mutation_allowed=True,
        capex_budget=120_000_000.0,
        hire_slots=2,
    ),
}

SCENARIO_TITLES = {
    "scenario_01": "Realokasi SDM Murni",
    "scenario_02": "Substitusi Otomasi",
    "scenario_03": "Full Optimization",
}

SCENARIO_DESCRIPTIONS = {
    "scenario_01": (
        "Optimasi tanpa rekrut dan tanpa otomasi baru — hanya redistribusi "
        "operator yang sudah ada ke pos dengan kompatibilitas tertinggi."
    ),
    "scenario_02": (
        "Mesin otomatis mengambil alih pos manual dengan antrean tertinggi. "
        "Rekrut tetap dilarang, mutasi diizinkan."
    ),
    "scenario_03": (
        "Rekrut, mutasi, dan otomasi semuanya aktif — solusi terbaik tanpa "
        "batasan SDM maupun konfigurasi mesin."
    ),
}

METRIC_KEYS = (
    "throughput_per_hour",
    "human_error_rate_pct",
    "total_op_cost_per_hour_rp",
    "cost_per_item_rp",
)

LOWER_IS_BETTER = {
    "human_error_rate_pct",
    "total_op_cost_per_hour_rp",
    "cost_per_item_rp",
}

WEIGHT_SWEEP = np.array(
    [
        [0.40, 0.20, 0.25, 0.15],
        [0.55, 0.15, 0.15, 0.15],
        [0.25, 0.40, 0.20, 0.15],
        [0.25, 0.15, 0.45, 0.15],
        [0.30, 0.15, 0.20, 0.35],
        [0.45, 0.25, 0.20, 0.10],
        [0.20, 0.30, 0.35, 0.15],
    ],
    dtype=np.float32,
)


@dataclass
class TrainingConfig:
    total_timesteps: int = 2_000_000
    n_envs: int = 8
    n_steps: int = 512
    batch_size: int = 256
    n_epochs: int = 10
    learning_rate: float = 3e-4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_range: float = 0.2
    ent_coef: float = 0.01
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5
    eval_freq: int = 20_000
    seed: int = 42
    parallel_scenarios: bool = True
    output_dir: Path = Path("training/outputs")


def linear_schedule(initial: float):
    def schedule(progress_remaining: float) -> float:
        return progress_remaining * initial

    return schedule


def load_snapshot(
    factory_path: Path,
    worker_path: Path,
    init_path: Path,
    simulation_path: Optional[Path] = None,
):
    factory = json.loads(factory_path.read_text(encoding="utf-8"))
    workers = json.loads(worker_path.read_text(encoding="utf-8"))
    init_state = json.loads(init_path.read_text(encoding="utf-8"))
    simulation = (
        json.loads(simulation_path.read_text(encoding="utf-8"))
        if simulation_path is not None
        else None
    )

    builder = SnapshotBuilder(
        factory_md=factory,
        worker_md=workers,
        init_state=init_state,
        simulation_state=simulation,
    )
    return builder.build()


def mask_function(env: FactoryOptimizationEnv) -> np.ndarray:
    return env.action_masks()


def make_env(
    snapshot,
    scenario: ScenarioConstraints,
    seed: int,
    rank: int,
    sample_weights: bool = True,
    randomize_start: bool = True,
):
    def initializer():
        env = FactoryOptimizationEnv(
            snapshot=snapshot,
            scenario=scenario,
            params=HumanFactorsParams(),
            sample_weights=sample_weights,
            randomize_start=randomize_start,
            seed=seed + rank,
        )
        env = ActionMasker(env, mask_function)
        env = Monitor(env)
        env.reset(seed=seed + rank)
        return env

    return initializer


def build_vector_env(
    snapshot,
    scenario: ScenarioConstraints,
    config: TrainingConfig,
    training: bool = True,
):
    builders = [
        make_env(snapshot, scenario, config.seed, rank) for rank in range(config.n_envs)
    ]
    vector = SubprocVecEnv(builders) if config.n_envs > 1 else DummyVecEnv(builders)
    return VecNormalize(
        vector,
        training=training,
        norm_obs=False,
        norm_reward=True,
        clip_reward=10.0,
        gamma=config.gamma,
    )


def build_model(vector_env, config: TrainingConfig) -> MaskablePPO:
    policy_kwargs = dict(
        net_arch=dict(pi=[512, 256, 128], vf=[512, 256, 128]),
        activation_fn=nn.Tanh,
        ortho_init=True,
    )

    return MaskablePPO(
        policy=MaskableActorCriticPolicy,
        env=vector_env,
        learning_rate=linear_schedule(config.learning_rate),
        n_steps=config.n_steps,
        batch_size=config.batch_size,
        n_epochs=config.n_epochs,
        gamma=config.gamma,
        gae_lambda=config.gae_lambda,
        clip_range=config.clip_range,
        ent_coef=config.ent_coef,
        vf_coef=config.vf_coef,
        max_grad_norm=config.max_grad_norm,
        policy_kwargs=policy_kwargs,
        tensorboard_log=str(config.output_dir / "tensorboard"),
        seed=config.seed,
        device="auto",
        verbose=1,
    )


def train(snapshot, scenario_id: str, config: TrainingConfig) -> MaskablePPO:
    set_random_seed(config.seed)
    scenario = SCENARIO_LIBRARY[scenario_id]

    config.output_dir.mkdir(parents=True, exist_ok=True)

    train_env = build_vector_env(snapshot, scenario, config, training=True)
    eval_env = build_vector_env(snapshot, scenario, config, training=False)
    eval_env.obs_rms = train_env.obs_rms

    callback = MaskableEvalCallback(
        eval_env,
        best_model_save_path=str(config.output_dir / scenario_id / "best"),
        log_path=str(config.output_dir / scenario_id / "eval"),
        eval_freq=max(config.eval_freq // config.n_envs, 1),
        n_eval_episodes=10,
        deterministic=True,
    )

    model = build_model(train_env, config)
    model.learn(total_timesteps=config.total_timesteps, callback=callback)

    model.save(str(config.output_dir / scenario_id / "policy"))
    train_env.save(str(config.output_dir / scenario_id / "vecnormalize.pkl"))
    train_env.close()
    eval_env.close()
    return model


def rollout(
    model: MaskablePPO,
    snapshot,
    scenario: ScenarioConstraints,
    weights: RewardWeights,
    seed: int = 0,
) -> dict[str, Any]:
    env = FactoryOptimizationEnv(
        snapshot=snapshot,
        scenario=scenario,
        sample_weights=False,
        randomize_start=False,
        seed=seed,
    )
    observation, info = env.reset(seed=seed, options={"weights": weights})

    terminated = False
    total_reward = 0.0

    while not terminated:
        masks = env.action_masks()
        action, _ = model.predict(observation, action_masks=masks, deterministic=True)
        observation, reward, terminated, truncated, info = env.step(action)
        total_reward += reward

    info["episode_reward"] = total_reward
    env.close()
    return info


def to_station_id(snapshot, index: int) -> Optional[str]:
    if index < 0:
        return None
    return snapshot.maps.station_ids[index]


def to_worker_id(snapshot, index: int) -> str:
    if index < snapshot.maps.n_workers:
        return snapshot.maps.worker_ids[index]
    return f"wrk-new-{index - snapshot.maps.n_workers + 1:02d}"


def to_worker_name(snapshot, index: int) -> str:
    if index < snapshot.maps.n_workers:
        return snapshot.maps.worker_names[index]
    return "TBD - Operator Baru"


def to_asset_id(snapshot, index: int) -> str:
    return snapshot.maps.asset_ids[index]


def build_scenario_payload(
    snapshot,
    scenario_id: str,
    scenario: ScenarioConstraints,
    weights: RewardWeights,
    info: dict[str, Any],
) -> dict[str, Any]:
    breakdown = info["breakdown"]
    baselines = snapshot.baselines

    baseline_cost_hour = baselines.cost_per_item * max(baselines.good_throughput, 1e-6)
    after_cost_hour = breakdown["cost_per_item"] * max(breakdown["good_throughput"], 1e-6)

    positions = []
    moves = []

    for index in range(len(info["assignment"])):
        if not info["active"][index]:
            continue

        origin = int(info["initial_assignment"][index])
        target = int(info["assignment"][index])
        worker_id = to_worker_id(snapshot, index)

        positions.append(
            {
                "worker_id": worker_id,
                "name": to_worker_name(snapshot, index),
                "current_station_rightnow": to_station_id(snapshot, origin),
                "optimal_station": to_station_id(snapshot, target),
                "action": "stay" if origin == target else "moved",
                "projected_fatigue": round(float(info["fatigue"][index]), 4),
                "projected_stress": round(float(info["stress"][index]), 4),
            }
        )

        if origin == target:
            continue

        move_id = f"move-{len(moves) + 1:02d}"
        positions[-1]["move_id"] = move_id
        moves.append(
            {
                "move_id": move_id,
                "worker_id": worker_id,
                "name": to_worker_name(snapshot, index),
                "from_station": to_station_id(snapshot, origin),
                "to_station": to_station_id(snapshot, target),
                "final_fatigue": round(float(info["fatigue"][index]), 4),
                "final_stress": round(float(info["stress"][index]), 4),
            }
        )

    params = HumanFactorsParams()

    upgrades = [
        {
            "asset_id": to_asset_id(snapshot, entry["station_index"]),
            "workflow_step": to_station_id(snapshot, entry["station_index"]),
            "is_automated": True,
            "capex_rp": params.automation_capex,
        }
        for entry in info["upgrades"]
    ]

    hires = [
        {
            "worker_id": to_worker_id(snapshot, entry["worker_index"]),
            "name": to_worker_name(snapshot, entry["worker_index"]),
            "assigned_station": to_station_id(snapshot, entry["station_index"]),
            "capex_rp": params.hire_capex,
        }
        for entry in info["hires"]
    ]

    residual = [
        to_station_id(snapshot, int(index))
        for index in np.flatnonzero(
            info["station_potential"] < snapshot.constraints.target_line_rate * 0.98
        )
    ]

    return {
        "scenario_id": scenario_id,
        "title": SCENARIO_TITLES.get(scenario_id, scenario_id),
        "description": SCENARIO_DESCRIPTIONS.get(scenario_id, ""),
        "reward_weights": weights.as_dict(),
        "constraints": {
            "hiring_allowed": scenario.hiring_allowed,
            "fire_or_mutation_allowed": scenario.mutation_allowed,
            "automation_allowed": scenario.automation_allowed,
            "capex_rp": float(scenario.capex_budget),
            "capex_used_rp": float(info["capex_spent"]),
        },
        "metrics": {
            "throughput_per_hour": {
                "before": round(baselines.good_throughput, 2),
                "after": round(breakdown["good_throughput"], 2),
            },
            "human_error_rate_pct": {
                "before": round(baselines.error_rate * 100.0, 2),
                "after": round(breakdown["error_rate"] * 100.0, 2),
            },
            "total_op_cost_per_hour_rp": {
                "before": round(baseline_cost_hour, 2),
                "after": round(after_cost_hour, 2),
            },
            "cost_per_item_rp": {
                "before": round(baselines.cost_per_item, 2),
                "after": round(breakdown["cost_per_item"], 2),
            },
            "mean_fatigue": {"after": round(breakdown["mean_fatigue"], 4)},
            "max_fatigue": {"after": round(breakdown["max_fatigue"], 4)},
            "bottleneck_count": {"after": int(breakdown["bottleneck_count"])},
        },
        "factory_flow_optimal": {
            "reallocation_moves": moves,
            "asset_upgrades": upgrades,
            "new_hires": hires,
            "optimal_staff_positions": positions,
            "residual_bottleneck": residual[0] if residual else None,
        },
        "episode_reward": round(float(info["episode_reward"]), 4),
    }


def finalize_metrics(scenario: dict[str, Any]) -> None:
    metrics = scenario["metrics"]

    for key in METRIC_KEYS:
        before = float(metrics[key]["before"])
        after = float(metrics[key]["after"])
        delta = 0.0 if abs(before) < 1e-9 else (after - before) / abs(before) * 100.0
        improved = after < before if key in LOWER_IS_BETTER else after > before

        metrics[key]["delta_pct"] = round(delta, 2)
        metrics[key]["direction"] = "up" if delta > 0 else "down"
        metrics[key]["is_improvement"] = bool(improved)


def build_insight(scenario: dict[str, Any]) -> str:
    metrics = scenario["metrics"]
    flow = scenario["factory_flow_optimal"]

    throughput = metrics["throughput_per_hour"]["delta_pct"]
    cost = metrics["cost_per_item_rp"]["delta_pct"]
    capex = scenario["constraints"]["capex_used_rp"]

    parts = [
        f"Throughput {throughput:+.1f}% dengan biaya per unit {cost:+.1f}%.",
        f"{len(flow['reallocation_moves'])} rotasi staf",
        f"{len(flow['asset_upgrades'])} upgrade aset",
        f"{len(flow['new_hires'])} rekrut baru.",
    ]

    if capex > 0:
        parts.append(f"Capex terpakai Rp {capex:,.0f}.".replace(",", "."))
    else:
        parts.append("Tanpa capex sama sekali.")

    if flow["residual_bottleneck"]:
        parts.append(f"Bottleneck tersisa di {flow['residual_bottleneck']}.")
    else:
        parts.append("Tidak ada bottleneck tersisa.")

    return " ".join(parts)


def select_scenario_payload(
    snapshot,
    scenario_id: str,
    model: MaskablePPO,
    config: TrainingConfig,
) -> dict[str, Any]:
    scenario = SCENARIO_LIBRARY[scenario_id]
    candidates = []

    for row in WEIGHT_SWEEP:
        weights = RewardWeights.from_vector(row)
        info = rollout(model, snapshot, scenario, weights, seed=config.seed)
        candidates.append(
            build_scenario_payload(snapshot, scenario_id, scenario, weights, info)
        )

    objectives = np.array(
        [
            [
                item["metrics"]["throughput_per_hour"]["after"],
                item["metrics"]["cost_per_item_rp"]["after"],
                item["metrics"]["max_fatigue"]["after"],
                item["metrics"]["bottleneck_count"]["after"],
            ]
            for item in candidates
        ],
        dtype=np.float64,
    )

    maximize = np.array([True, False, False, False])
    front = pareto_front(objectives, maximize)

    pool = [candidates[int(index)] for index in front] or candidates
    return max(pool, key=lambda item: item["episode_reward"])


def pick_recommended(scenarios: list[dict[str, Any]]) -> str:
    ranked = sorted(
        scenarios,
        key=lambda item: (
            item["constraints"]["capex_used_rp"],
            -item["metrics"]["throughput_per_hour"]["after"],
        ),
    )
    return ranked[0]["scenario_id"]


def export_scenarios(
    snapshot,
    models: dict[str, MaskablePPO],
    output_path: Path,
    config: TrainingConfig,
    factory_id: Optional[str] = None,
) -> dict[str, Any]:
    scenarios = [
        select_scenario_payload(snapshot, scenario_id, models[scenario_id], config)
        for scenario_id in SCENARIO_ORDER
        if scenario_id in models
    ]

    for scenario in scenarios:
        finalize_metrics(scenario)
        scenario["insight"] = build_insight(scenario)

    recommended_id = pick_recommended(scenarios)
    for scenario in scenarios:
        scenario["recommended"] = scenario["scenario_id"] == recommended_id

    payload = {
        "hasil_optimisasi_skenario_optimal": {
            "meta": {
                "status": "RL CONVERGED",
                "algorithm": "Maskable PPO (sb3-contrib)",
                "total_timesteps": config.total_timesteps,
                "factory_id": factory_id,
                "recommended_scenario_id": recommended_id,
                "baseline": {
                    "throughput_per_hour": round(snapshot.baselines.good_throughput, 2),
                    "human_error_rate_pct": round(snapshot.baselines.error_rate * 100.0, 2),
                    "cost_per_item_rp": round(snapshot.baselines.cost_per_item, 2),
                },
            },
            "scenarios": scenarios,
        }
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return payload


def _train_scenario_task(
    snapshot, scenario_id: str, config: TrainingConfig
) -> tuple[str, str]:
    train(snapshot, scenario_id, config)
    return scenario_id, str(config.output_dir / scenario_id / "policy.zip")


def train_all_scenarios(
    snapshot, config: TrainingConfig
) -> dict[str, MaskablePPO]:
    if not config.parallel_scenarios:
        return {
            scenario_id: train(snapshot, scenario_id, config)
            for scenario_id in SCENARIO_ORDER
        }

    per_scenario = replace(
        config, n_envs=max(1, config.n_envs // len(SCENARIO_ORDER))
    )

    paths: dict[str, str] = {}
    with ProcessPoolExecutor(max_workers=len(SCENARIO_ORDER)) as pool:
        futures = {
            pool.submit(_train_scenario_task, snapshot, scenario_id, per_scenario): scenario_id
            for scenario_id in SCENARIO_ORDER
        }
        for future in as_completed(futures):
            scenario_id, path = future.result()
            paths[scenario_id] = path

    device = "cuda" if torch.cuda.is_available() else "cpu"
    return {
        scenario_id: MaskablePPO.load(paths[scenario_id], device=device)
        for scenario_id in SCENARIO_ORDER
    }


def resolve_output_path(factory_id: Optional[str], explicit: Optional[Path]) -> Path:
    if explicit is not None:
        return explicit
    if factory_id:
        return Path("outputs/rl") / factory_id / "optimal_state.json"
    return Path("training/outputs/optimal_state.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Latih ketiga skenario RL sekaligus dan ekspor hasilnya."
    )
    parser.add_argument("--factory-id", default=None)
    parser.add_argument("--input-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--timesteps", type=int, default=None)
    parser.add_argument("--n-envs", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--sequential", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    config = TrainingConfig(parallel_scenarios=not args.sequential)
    if args.timesteps is not None:
        config.total_timesteps = args.timesteps
    if args.n_envs is not None:
        config.n_envs = args.n_envs
    if args.seed is not None:
        config.seed = args.seed

    snapshot = load_snapshot(
        factory_path=args.input_dir / "factory_md.json",
        worker_path=args.input_dir / "worker_md.json",
        init_path=args.input_dir / "init_state.json",
        simulation_path=args.input_dir / "simulation_state.json",
    )

    models = train_all_scenarios(snapshot, config)

    export_scenarios(
        snapshot=snapshot,
        models=models,
        output_path=resolve_output_path(args.factory_id, args.output),
        config=config,
        factory_id=args.factory_id,
    )


if __name__ == "__main__":
    main()