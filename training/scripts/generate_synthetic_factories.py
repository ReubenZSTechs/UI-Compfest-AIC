"""
Bootstraps synthetic factory "digital twin" seed files: factory_info + assets
+ job_descriptions (factory_md_schema.json) merged with workers
(worker_md_schema.json) into one JSON doc per factory - the exact input
shape Training_sample_generator.py's flatten_pair_items() expects
(doc['assets'], doc['job_descriptions'], doc['workers']).

This is pure structural/randomized generation (no LLM call) because at this
stage there's no real factory to describe yet - it just needs to be
schema-valid so the LLM-compatibility-evaluation pipeline has something to
run on. Run this once to populate INPUT_DIR, then run
`python -m training.scripts.Training_sample_generator` as before.
"""

import json
import random
from pathlib import Path

random.seed(42)

OUTPUT_DIR = Path("./training/data/formatted/syntetic_factories/")
NUM_FACTORIES = 4
WORKER_POOL_SIZE_RANGE = (8, 14)

STEP_POOL = [
    "Raw Material Intake",
    "Cutting",
    "Machining",
    "Assembly",
    "Surface Treatment",
    "Quality Inspection",
    "Packaging",
    "Palletizing",
]

STEP_CATEGORY_BIAS = {
    "Raw Material Intake": ["conveyor_automation", "manual_station"],
    "Cutting": ["machine"],
    "Machining": ["machine"],
    "Assembly": ["manual_station", "machine"],
    "Surface Treatment": ["environmental_chamber", "machine"],
    "Quality Inspection": ["measuring_equipment"],
    "Packaging": ["conveyor_automation", "manual_station"],
    "Palletizing": ["conveyor_automation", "manual_station"],
}

ASSET_NAME_TEMPLATES = {
    "machine": ["CNC Mill {n}", "Hydraulic Press {n}", "Injection Molder {n}", "Lathe Station {n}"],
    "measuring_equipment": ["Coordinate Measuring Machine {n}", "Digital Caliper Rig {n}", "Vision Inspection System {n}"],
    "conveyor_automation": ["Belt Conveyor {n}", "Robotic Pick-and-Place {n}", "AGV Transport Unit {n}"],
    "environmental_chamber": ["Curing Oven {n}", "Humidity Chamber {n}", "Thermal Cycling Chamber {n}"],
    "manual_station": ["Manual Assembly Bench {n}", "Hand-Pack Station {n}", "Inspection Table {n}"],
}

JOB_TITLE_TEMPLATES = {
    "Raw Material Intake": "Material Handler",
    "Cutting": "Cutting Operator",
    "Machining": "Machine Operator",
    "Assembly": "Assembly Technician",
    "Surface Treatment": "Surface Treatment Operator",
    "Quality Inspection": "QC Inspector",
    "Packaging": "Packaging Operator",
    "Palletizing": "Palletizing Operator",
}

FIRST_NAMES = ["Andi", "Budi", "Citra", "Dewi", "Eka", "Farid", "Gita", "Hari",
               "Indra", "Joko", "Kartika", "Lestari", "Made", "Nia", "Oscar", "Putri"]
LAST_NAMES = ["Saputra", "Wijaya", "Kusuma", "Pratama", "Santoso", "Halim",
              "Wibowo", "Hidayat", "Permana", "Setiawan"]


def gen_factory_info(idx: int, workflow_sequence: list, process_type: str) -> dict:
    parallel_groups = []
    if process_type == "parallel" and len(workflow_sequence) >= 2:
        group_size = min(2, len(workflow_sequence))
        group_steps = random.sample(workflow_sequence, group_size)
        parallel_groups.append({
            "group_id": f"PG-{idx:02d}-01",
            "steps": group_steps,
            "reasoning": (
                f"Steps {', '.join(group_steps)} do not share equipment or "
                f"line dependencies, so they can run concurrently without "
                f"blocking one another."
            ),
        })
    return {
        "factory_id": f"FCT-{idx:04d}",
        "factory_name": f"Synthetic Plant {idx}",
        "process_type": process_type,
        "declared_worker_count": None,  # filled in after workers are generated
        "layout_description": (
            f"A {process_type} production line laid out along the sequence "
            f"{' -> '.join(workflow_sequence)}, with stations grouped by "
            f"workflow step."
        ),
        "workflow_sequence": workflow_sequence,
        "parallel_groups": parallel_groups,
    }


def gen_assets(idx: int, workflow_sequence: list) -> list:
    assets = []
    counter = 1
    for step in workflow_sequence:
        n_assets = random.randint(1, 2)
        categories = STEP_CATEGORY_BIAS.get(step, ["machine"])
        for _ in range(n_assets):
            category = random.choice(categories)
            name_template = random.choice(ASSET_NAME_TEMPLATES[category])
            asset_id = f"AST-{idx:04d}-{counter:03d}"
            is_automated = category in ("conveyor_automation", "machine") and random.random() < 0.7
            assets.append({
                "asset_id": asset_id,
                "asset_name": name_template.format(n=counter),
                "category": category,
                "workflow_step": step,
                "is_automated": is_automated,
                "units_available": random.randint(1, 4),
                "base_throughput_capacity": random.randint(20, 300),
                "operational_cost_per_hour": round(random.uniform(5.0, 120.0), 2),
                "environmental_factors": {
                    "noise_level_db": random.randint(35, 92),
                    "vibration_hazard_level": random.choices(
                        ["low", "medium", "high"], weights=[0.5, 0.35, 0.15]
                    )[0],
                    "physical_strain_index": round(random.uniform(0.05, 0.9), 2),
                },
                "metric_derivation_reasoning": (
                    f"Synthetic baseline for a {category.replace('_', ' ')} used at the "
                    f"'{step}' step; throughput and cost sampled within typical ranges "
                    f"for this equipment class."
                ),
            })
            counter += 1
    return assets


def gen_jobs(idx: int, workflow_sequence: list, assets: list, worker_ids: list) -> list:
    jobs = []
    counter = 1
    assets_by_step = {}
    for a in assets:
        assets_by_step.setdefault(a["workflow_step"], []).append(a)

    error_weights = {"low": 0.4, "moderate": 0.35, "high": 0.2, "critical": 0.05}
    physical_weights = {"low": 0.4, "medium": 0.4, "high": 0.2}

    for step in workflow_sequence:
        step_assets = assets_by_step.get(step, [])
        if not step_assets:
            continue
        n_jobs = random.randint(1, min(2, len(step_assets)))
        chosen_assets = random.sample(step_assets, n_jobs)
        for asset in chosen_assets:
            job_id = f"JOB-{idx:04d}-{counter:03d}"
            n_assigned = random.randint(1, 2)
            assigned = random.sample(worker_ids, min(n_assigned, len(worker_ids)))
            error_severity = random.choices(list(error_weights), weights=list(error_weights.values()))[0]
            physical_demand = random.choices(list(physical_weights), weights=list(physical_weights.values()))[0]
            jobs.append({
                "job_id": job_id,
                "job_title": JOB_TITLE_TEMPLATES.get(step, f"{step} Operator"),
                "workflow_step": step,
                "assigned_asset_id": asset["asset_id"],
                "assigned_worker_name": assigned,
                "demands": {
                    "required_cognitive_focus": round(random.uniform(0.1, 0.95), 2),
                    "physical_demand_level": physical_demand,
                    "task_complexity": round(random.uniform(0.1, 0.95), 2),
                    "error_severity": error_severity,
                },
                "qc_requirement": (
                    f"Visual and dimensional check against spec after each unit "
                    f"processed on {asset['asset_name']}."
                ),
                "metric_derivation_reasoning": (
                    f"Demand levels sampled to reflect a {physical_demand} physical, "
                    f"{error_severity}-severity task typical of the '{step}' step."
                ),
            })
            counter += 1
    return jobs


def gen_workers(idx: int, pool_size: int) -> list:
    workers = []
    used_names = set()
    for i in range(1, pool_size + 1):
        while True:
            name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
            if name not in used_names:
                used_names.add(name)
                break
        worker_id = f"WKR-{idx:04d}-{i:03d}"
        experience = random.randint(0, 20)
        workers.append({
            "worker_id": worker_id,
            "name": name,
            "demographics": {
                "age": random.randint(18, 60),
                "gender": random.choices(["male", "female", "unspecified"], weights=[0.48, 0.48, 0.04])[0],
                "years_of_experience": experience,
                "baseline_physical_stamina": round(random.uniform(0.3, 1.0), 2),
                "cognitive_resilience": round(random.uniform(0.3, 1.0), 2),
            },
            "shift_context": {
                "hours_worked_today": round(random.uniform(0, 10), 1),
                "consecutive_shifts": random.randint(0, 6),
            },
        })
    return workers


def gen_factory(idx: int) -> dict:
    n_steps = random.randint(4, 6)
    workflow_sequence = random.sample(STEP_POOL, n_steps)
    process_type = random.choices(["serial", "parallel"], weights=[0.6, 0.4])[0]

    pool_size = random.randint(*WORKER_POOL_SIZE_RANGE)
    workers = gen_workers(idx, pool_size)
    worker_ids = [w["worker_id"] for w in workers]

    factory_info = gen_factory_info(idx, workflow_sequence, process_type)
    assets = gen_assets(idx, workflow_sequence)
    jobs = gen_jobs(idx, workflow_sequence, assets, worker_ids)

    factory_info["declared_worker_count"] = len(workers)

    return {
        "factory_info": factory_info,
        "assets": assets,
        "job_descriptions": jobs,
        "workers": workers,
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for idx in range(1, NUM_FACTORIES + 1):
        doc = gen_factory(idx)
        out_path = OUTPUT_DIR / f"factory_{idx:04d}.json"
        out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(out_path)
        print(f"wrote {out_path} "
              f"({len(doc['assets'])} assets, {len(doc['job_descriptions'])} jobs, "
              f"{len(doc['workers'])} workers)")
    return written


if __name__ == "__main__":
    main()

    # python -m training.scripts.generate_synthetic_factories