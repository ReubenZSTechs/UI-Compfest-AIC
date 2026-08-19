from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np
import torch
import torch.nn as nn
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.callbacks import MaskableEvalCallback
from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy
from sb3_contrib.common.maskable.utils import get_action_masks
from sb3_contrib.common.wrappers import ActionMasker
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.utils import set_random_seed
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecNormalize

from backend.app.optimization.factory_env import FactoryOptimizationEnv, HumanFactorsParams, ScenarioConstraints
from backend.app.optimization.reward_function import RewardWeights, pareto_front
from backend.app.services.snapshot_builder import SnapshotBuilder

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

        if origin != target:
            moves.append(
                {
                    "move_id": f"move-{len(moves) + 1:02d}",
                    "worker_id": worker_id,
                    "name": to_worker_name(snapshot, index),
                    "from_station": to_station_id(snapshot, origin),
                    "to_station": to_station_id(snapshot, target),
                    "final_fatigue": round(float(info["fatigue"][index]), 4),
                    "final_stress": round(float(info["stress"][index]), 4),
                }
            )

    upgrades = [
        {
            "asset_id": to_asset_id(snapshot, entry["station_index"]),
            "workflow_step": to_station_id(snapshot, entry["station_index"]),
            "is_automated": True,
            "capex_rp": HumanFactorsParams().automation_capex,
        }
        for entry in info["upgrades"]
    ]

    hires = [
        {
            "worker_id": to_worker_id(snapshot, entry["worker_index"]),
            "name": to_worker_name(snapshot, entry["worker_index"]),
            "assigned_station": to_station_id(snapshot, entry["station_index"]),
            "capex_rp": HumanFactorsParams().hire_capex,
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
        "reward_weights": weights.as_dict(),
        "constraints": {
            "hiring_allowed": scenario.hiring_allowed,
            "fire_or_mutation_allowed": scenario.mutation_allowed,
            "automation_allowed": scenario.automation_allowed,
            "capex_rp": scenario.capex_budget,
            "capex_used_rp": info["capex_spent"],
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
            "bottleneck_count": {"after": breakdown["bottleneck_count"]},
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


def sweep_and_export(
    snapshot,
    models: dict[str, MaskablePPO],
    output_path: Path,
    config: TrainingConfig,
) -> dict[str, Any]:
    candidates = []

    for scenario_id, model in models.items():
        scenario = SCENARIO_LIBRARY[scenario_id]
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
    selected = pareto_front(objectives, maximize)

    scenarios = [candidates[int(index)] for index in selected]
    scenarios.sort(key=lambda item: item["metrics"]["throughput_per_hour"]["after"], reverse=True)

    for item in scenarios:
        for key in ("throughput_per_hour", "human_error_rate_pct", "total_op_cost_per_hour_rp"):
            before = item["metrics"][key]["before"]
            after = item["metrics"][key]["after"]
            delta = 0.0 if abs(before) < 1e-9 else (after - before) / abs(before) * 100.0
            item["metrics"][key]["delta_pct"] = round(delta, 2)

    recommended = min(
        scenarios,
        key=lambda item: (
            item["constraints"]["capex_used_rp"],
            -item["metrics"]["throughput_per_hour"]["after"],
        ),
    )

    payload = {
        "hasil_optimisasi_skenario_optimal": {
            "meta": {
                "status": "RL CONVERGED",
                "algorithm": "Maskable PPO (sb3-contrib)",
                "total_timesteps": config.total_timesteps,
                "recommended_scenario_id": recommended["scenario_id"],
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


def main() -> None:
    config = TrainingConfig()

    snapshot = load_snapshot(
        factory_path=Path("outputs/factory_md.json"),
        worker_path=Path("outputs/worker_md.json"),
        init_path=Path("outputs/init_state.json"),
        simulation_path=Path("outputs/simulation_state.json"),
    )

    models = {}
    for scenario_id in SCENARIO_LIBRARY:
        models[scenario_id] = train(snapshot, scenario_id, config)

    sweep_and_export(
        snapshot=snapshot,
        models=models,
        output_path=config.output_dir / "optimal_state.json",
        config=config,
    )


if __name__ == "__main__":
    main()