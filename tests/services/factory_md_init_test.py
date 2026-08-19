import json
import sys
import time
from pathlib import Path
import copy
import re
from concurrent.futures import ThreadPoolExecutor

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"

for p in (str(PROJECT_ROOT), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pandas as pd
import streamlit as st

from backend.app.core.agent_config import get_agent_settings
from backend.app.services.agent_registry_service import AgentRole, get_agent_registry
from backend.app.services.extract_input_field_service import (
    UnsupportedDocumentError,
    build_any_agent_input,
    extract_any,
    is_workbook
)

from backend.app.services.validate_workbook_service import (
    validate_workbook
)

from backend.app.services.extract_worker_archive_service import (
    ArchiveError,
    extract_worker_uploads,
)
from backend.app.services.cv_pdf_parser_service import (
    build_worker_agent_input,
)
from backend.app.services.cross_reference_job_worker_service import (
    CompatibilityEvaluationError,
    generate_compatibility_matrix,
    read_jobs,
)
from backend.app.services.check_factory_completeness import (
    GapSeverity,
    check_factory_completeness,
)

from backend.app.services.extract_xlsx_input_service import (
    UnsupportedWorkbookError,
    build_agent_input as build_workbook_agent_input,
    extract_workbook,
    build_workbook,
    apply_repairs,
    workbook_as_dict,
)

from backend.app.services.generate_worker_profiles_service import (
    WorkerProfileGenerationError,
    generate_worker_profiles
)

from backend.app.services.floor_state_normalizer_service import (
    FloorStateAlignmentError,
    build_env_snapshot,
    normalize_floor_state,
)

from backend.app.services.cv_pdf_parser_service import candidate_payload
from backend.app.services.call_llm_service import LLMOutputTruncatedError

import numpy as np
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.utils import set_random_seed
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

from backend.app.services.snapshot_builder import SnapshotBuilder
from backend.app.optimization.factory_env import FactoryOptimizationEnv, HumanFactorsParams
from backend.app.optimization.reward_function import RewardWeights, pareto_front
from backend.app.optimization.train_ppo import (
    SCENARIO_LIBRARY,
    SCENARIO_TITLES,
    TrainingConfig,
    build_model,
    build_scenario_payload,
    mask_function,
    rollout,
)

import json
from pathlib import Path

from backend.app.services.create_factory_md_parallel import (
    ShardGenerationError,
    generate_factory_structure,
    shard_schema
)

from jsonschema import Draft202012Validator
from backend.app.services.usage_metrics_service import clone_usage


UPLOAD_DIR = Path("/tmp/pabrikers_playground")
STAGE_KEYS = [
    "extracted_source",
    "validation_report",
    "workbook_dict",
    "agent_input",
    "factory_structure",
    "factory_structure_meta",
    "completeness_report",
    "clarification_text",
    "worker_document",
    "worker_archive_reports",
    "worker_agent_input",
    "worker_profile",
    "compatibility_matrix",
    "floor_state",
    "floor_alignment_report",
    "simulation_state",
    "env_snapshot",
    "rl_policy",
    "rl_policy_scenario",
    "rl_scenarios",
    "rl_candidates",
    "optimal_state",
]

CHAT_ROUTES = ("twin_analyst", "scenario_explainer", "general")

CHAT_ROUTE_AGENTS = {
    "twin_analyst": AgentRole.CHATBOT_TWIN_ANALYST,
    "scenario_explainer": AgentRole.CHATBOT_SCENARIO_EXPLAINER,
    "general": AgentRole.CHATBOT_GENERAL,
}

CHAT_ROUTE_LABELS = {
    "twin_analyst": "Analis kondisi lini saat ini",
    "scenario_explainer": "Penjelas skenario optimasi",
    "general": "Asisten platform",
}

CHAT_HISTORY_WINDOW = 6
CHAT_SUMMARY_TRIGGER = 8

RL_OUTPUT_DIR = Path("/tmp/pabrikers_rl")

AUTOMATED_TOKENS = {"automatic", "automated", "full", "full_automatic", "otomatis", "penuh"}

DEFAULT_DEMANDS = {
    "required_cognitive_focus": 0.5,
    "physical_demand_level": "medium",
    "task_complexity": 0.4,
    "error_severity": "moderate",
}

DEFAULT_EVALUATIONS = {
    "overall_compatibility_score": 0.6,
    "throughput_multiplier": 1.0,
    "error_multiplier": 1.0,
    "fatigue_accumulation_rate": 0.7,
    "stress_sensitivity_factor": 0.7,
}

WEIGHT_PRESETS = {
    "Seimbang": (0.40, 0.20, 0.25, 0.15),
    "Kejar throughput": (0.55, 0.15, 0.15, 0.15),
    "Tekan biaya": (0.25, 0.40, 0.20, 0.15),
    "Lindungi pekerja": (0.25, 0.15, 0.45, 0.15),
    "Bongkar bottleneck": (0.30, 0.15, 0.20, 0.35),
}


import json
from typing import Any

from jsonschema import Draft7Validator


class StageIdMismatchError(ValueError):
    pass


def load_schema(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_init_state_shape(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))

    if errors:
        details = [f"{list(error.path)}: {error.message}" for error in errors]
        raise ValueError("Struktur init_state tidak sesuai schema:\n" + "\n".join(details))


def validate_stage_ids(payload: dict[str, Any], workflow_sequence: list[str]) -> None:
    canonical = set(workflow_sequence)
    terminal_targets = canonical | {"finished_goods_storage", None}
    positions = payload["factory_flow_rightnow"]["staff_current_positions"]

    for position in positions:
        worker_id = position["worker_id"]
        current_stage_id = position["current_stage_id"]
        next_stage_id = position["moving_to_next_stage_id"]

        if current_stage_id not in canonical:
            raise StageIdMismatchError(
                f"Worker {worker_id} punya current_stage_id '{current_stage_id}' "
                f"yang tidak ada di workflow_sequence: {sorted(canonical)}"
            )

        if next_stage_id not in terminal_targets:
            raise StageIdMismatchError(
                f"Worker {worker_id} punya moving_to_next_stage_id '{next_stage_id}' "
                f"yang tidak dikenal: {sorted(canonical | {'finished_goods_storage'})}"
            )


def validate_init_state(payload: dict[str, Any], schema: dict[str, Any], workflow_sequence: list[str]) -> None:
    validate_init_state_shape(payload, schema)
    validate_stage_ids(payload, workflow_sequence)


def normalize_route(raw) -> str:
    token = str(raw or "").strip().lower()
    token = re.sub(r"[\s\-]+", "_", token)
    token = re.sub(r"[^a-z_]", "", token)

    if token in CHAT_ROUTES:
        return token

    for route in CHAT_ROUTES:
        if route in token:
            return route

    return "general"


def slim_asset(asset: dict) -> dict:
    environment = asset.get("environmental_factors") or {}
    return {
        "asset_id": asset.get("asset_id"),
        "asset_name": asset.get("asset_name"),
        "category": asset.get("category"),
        "automation_level": asset.get("automation_level"),
        "units_available": asset.get("units_available"),
        "operational_cost_per_hour": asset.get("operational_cost_per_hour"),
        "noise_level_db": environment.get("noise_level_db"),
        "vibration_hazard_level": environment.get("vibration_hazard_level"),
        "physical_strain_index": environment.get("physical_strain_index"),
    }


def slim_stage(stage: dict) -> dict:
    return {
        "stage_id": stage.get("stage_id"),
        "stage_name": stage.get("stage_name"),
        "lane": stage.get("lane"),
        "next_stage_id": None if stage.get("is_terminal") else stage.get("next_stage_id"),
        "asset_id": stage.get("asset_id"),
        "flow_type": stage.get("flow_type"),
        "cycle_time_seconds": stage.get("cycle_time_seconds"),
        "throughput_per_hour": stage.get("throughput_per_hour"),
        "qc_requirement": stage.get("qc_requirement"),
    }


def slim_job(job: dict) -> dict:
    return {
        "job_id": job.get("job_id"),
        "job_title": job.get("job_title"),
        "stage_id": job_stage_id(job),
        "assigned_asset_id": job.get("assigned_asset_id"),
        "assigned_worker_ids": job.get("assigned_worker_ids"),
        "shift_id": job.get("shift_id"),
        "demands": job.get("demands"),
        "qc_requirement": job.get("qc_requirement"),
    }


def slim_worker(worker: dict) -> dict:
    return {
        "worker_id": worker.get("worker_id"),
        "name": worker.get("name"),
        "demographics": worker.get("demographics"),
        "shift_context": worker.get("shift_context"),
    }


def build_twin_context(twin, workers, floor, simulation) -> dict:
    context = {}

    if twin:
        info = twin.get("factory_info") or {}
        context["factory_info"] = {
            "factory_name": info.get("factory_name"),
            "process_type": info.get("process_type"),
            "workflow_sequence": info.get("workflow_sequence"),
            "lanes": info.get("lanes"),
            "parallel_groups": info.get("parallel_groups"),
        }
        context["shifts"] = twin.get("shifts")
        context["process_stages"] = [slim_stage(item) for item in twin.get("process_stages") or []]
        context["assets"] = [slim_asset(item) for item in twin.get("assets") or []]
        context["job_descriptions"] = [slim_job(item) for item in read_jobs(twin)]

    if workers:
        context["workers"] = [slim_worker(item) for item in workers.get("workers") or []]

    if floor:
        context["factory_flow_rightnow"] = floor.get("factory_flow_rightnow")
        context["llm_compatibility_and_evaluations"] = floor.get("llm_compatibility_and_evaluations")

    if simulation:
        context["live_simulation_state"] = simulation.get("live_simulation_state")

    return context


def build_scenario_context(optimal, simulation, twin) -> dict:
    context = {}

    if optimal:
        context["meta_description"] = optimal.get("meta_description")
        context["recommended_scenario_id"] = optimal.get("recommended_scenario_id")
        context["scenario_narratives"] = optimal.get("scenario_narratives")

    if simulation:
        context["live_simulation_state"] = simulation.get("live_simulation_state")

    if twin:
        context["process_stages"] = [slim_stage(item) for item in twin.get("process_stages") or []]

    return context


def build_chat_context(route, twin, workers, floor, simulation, optimal) -> dict:
    if route == "twin_analyst":
        return build_twin_context(twin, workers, floor, simulation)

    if route == "scenario_explainer":
        return build_scenario_context(optimal, simulation, twin)

    return {}


def format_route_payload(context: dict, question: str) -> str:
    if not context:
        return f"PERTANYAAN\n{question}"

    body = json.dumps(context, ensure_ascii=False, indent=2)
    return f"CONTEXT\n{body}\n\nPERTANYAAN\n{question}"


def format_rewriter_payload(summary, messages: list, question: str) -> str:
    blocks = []

    if summary:
        blocks.append(f"RINGKASAN PERCAKAPAN\n{summary}")

    recent = messages[-CHAT_HISTORY_WINDOW:]

    if recent:
        turns = "\n".join(
            f"{'Manajer' if item['role'] == 'user' else 'Asisten'}: {item['content']}"
            for item in recent
        )
        blocks.append(f"GILIRAN TERAKHIR\n{turns}")

    blocks.append(f"PESAN TERBARU\n{question}")
    return "\n\n".join(blocks)


def format_summarizer_payload(summary, messages: list) -> str:
    blocks = []

    if summary:
        blocks.append(f"RINGKASAN LAMA\n{summary}")

    turns = "\n".join(
        f"{'Manajer' if item['role'] == 'user' else 'Asisten'}: {item['content']}"
        for item in messages
    )
    blocks.append(f"GILIRAN BARU\n{turns}")
    return "\n\n".join(blocks)


def route_readiness(route, simulation, optimal):
    if route == "twin_analyst" and simulation is None:
        return ("Rute twin_analyst butuh state simulasi. "
                "Jalankan Agent D pada tab Pipeline lanjutan terlebih dahulu.")

    if route == "scenario_explainer" and not optimal:
        return ("Rute scenario_explainer butuh hasil optimasi. "
                "Jalankan Agent E pada tab Pipeline lanjutan terlebih dahulu.")

    return None


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def project_evaluations(matrix: dict, positions: list[dict], resolver) -> list[dict]:
    records = (matrix or {}).get("compatibility_matrix") or {}
    projected = []

    for position in positions:
        worker_id = str(position["worker_id"])
        stage_id = position["current_stage_id"]
        job = resolver.jobs.get(stage_id) or {}
        job_id = str(job.get("job_id") or "")
        entry = (records.get(worker_id) or {}).get("jobs", {}).get(job_id)

        if entry is None:
            continue

        projected.append({
            "worker_id": worker_id,
            "job_id": job_id,
            "stage_id": stage_id,
            "asset_id": position["current_asset_id"],
            "evaluations": entry["evaluations"],
            "llm_reasoning": entry["llm_reasoning"],
        })

    return projected


def run_floor_state_placement_only(payload: str) -> dict:
    settings = get_agent_settings()
    master = json.loads((Path(settings.schema_dir) / "init_state.schema.json").read_text(encoding="utf-8"))
    agent = get_agent_registry().get(AgentRole.INIT_STATE)

    started = time.perf_counter()
    result = agent.generate_structured(
        user_prompt=f"{payload}\n\nKembalikan HANYA field 'factory_flow_rightnow'.",
        schema_override=shard_schema(master, "factory_flow_rightnow", None),
    )
    record_bulk_metrics("floor_state", time.perf_counter() - started, clone_usage(agent.last_usage))

    return result


def run_chat_turn(question: str, twin, workers, floor, simulation, optimal) -> dict:
    registry = get_agent_registry()
    trace = {"pertanyaan": question}

    started = time.perf_counter()
    rewriter = registry.get(AgentRole.CHATBOT_QUERY_REWRITER)
    rewritten = rewriter.generate_response(
        user_prompt=format_rewriter_payload(
            st.session_state["chat_summary"], st.session_state["chat_messages"], question
        )
    ).strip()
    trace["rewrite_detik"] = round(time.perf_counter() - started, 2)
    trace["pertanyaan_ditulis_ulang"] = rewritten or question

    started = time.perf_counter()
    router = registry.get(AgentRole.CHATBOT_ROUTER)
    raw_route = router.generate_response(user_prompt=trace["pertanyaan_ditulis_ulang"])
    trace["route_detik"] = round(time.perf_counter() - started, 2)
    trace["route_mentah"] = str(raw_route).strip()
    trace["route"] = normalize_route(raw_route)

    gate = route_readiness(trace["route"], simulation, optimal)

    if gate is not None:
        trace["jawaban"] = gate
        trace["terblokir"] = True
        return trace

    context = build_chat_context(
        trace["route"], twin, workers, floor, simulation, optimal
    )
    payload = format_route_payload(context, trace["pertanyaan_ditulis_ulang"])
    trace["konteks_kunci"] = list(context.keys())
    trace["konteks_token_estimasi"] = estimate_tokens(payload)

    started = time.perf_counter()
    agent = registry.get(CHAT_ROUTE_AGENTS[trace["route"]])
    answer = agent.generate_response(user_prompt=payload)
    trace["jawab_detik"] = round(time.perf_counter() - started, 2)
    trace["jawaban"] = answer.strip()
    trace["terblokir"] = False

    record_metrics(f"chat_{trace['route']}", trace["jawab_detik"], agent)
    return trace


def compact_chat_history() -> None:
    messages = st.session_state["chat_messages"]

    if len(messages) <= CHAT_SUMMARY_TRIGGER:
        return

    folded = messages[:-CHAT_HISTORY_WINDOW]
    summarizer = get_agent_registry().get(AgentRole.CHATBOT_SUMMARIZER)

    summary = summarizer.generate_response(
        user_prompt=format_summarizer_payload(st.session_state["chat_summary"], folded)
    ).strip()

    st.session_state["chat_summary"] = summary
    st.session_state["chat_messages"] = messages[-CHAT_HISTORY_WINDOW:]


def init_session_state():
    for key in STAGE_KEYS:
        if key not in st.session_state:
            st.session_state[key] = None

    if "timings" not in st.session_state:
        st.session_state["timings"] = {}

    if "usages" not in st.session_state:
        st.session_state["usages"] = {}

    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []

    if "chat_summary" not in st.session_state:
        st.session_state['chat_summary'] = []

    if "chat_traces" not in st.session_state:
        st.session_state['chat_traces'] = []


def persist_upload(uploaded_file) -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target = UPLOAD_DIR / uploaded_file.name

    with open(target, "wb") as handle:
        handle.write(uploaded_file.getbuffer())

    return target


def record_metrics(stage: str, elapsed: float, agent) -> None:
    st.session_state["timings"][stage] = elapsed

    usage = getattr(agent, "last_usage", None)
    if usage is None:
        return

    st.session_state["usages"][stage] = {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def load_master_schema() -> dict:
    settings = get_agent_settings()
    return json.loads((Path(settings.schema_dir) / "factory_md.schema.json").read_text(encoding="utf-8"))


def record_bulk_metrics(stage: str, elapsed: float, usage: dict | None) -> None:
    st.session_state["timings"][stage] = elapsed

    if usage:
        st.session_state["usages"][stage] = usage


def run_factory_structure_parallel(payload: str, chunk_stage: int, chunk_wide: int,
                                   max_workers: int, max_attempts: int, shard_timeout_min: int,
                                   strict: bool) -> dict:
    agent = get_agent_registry().get(AgentRole.FACTORY_STRUCTURE)
    bar = st.progress(0.0, text="Menyusun kerangka tahapan...")

    def report(done: int, total: int, pending: list[str]) -> None:
        label = f"Shard {done}/{total}"
        if pending:
            shown = ", ".join(pending[:3]) + (" ..." if len(pending) > 3 else "")
            label += f" — menunggu: {shown}"
        bar.progress(done / total, text=label)

    started = time.perf_counter()

    try:
        result = generate_factory_structure(
            agent=agent,
            master_schema=load_master_schema(),
            payload=payload,
            workbook=st.session_state.get("workbook_dict"),
            stage_names=st.session_state.get("stage_names"),
            chunk_sizes={
                "process_stages": chunk_stage,
                "assets": chunk_wide,
                "job_descriptions": chunk_wide,
            },
            max_workers=max_workers,
            max_attempts=max_attempts,
            shard_timeout_seconds=shard_timeout_min * 60,
            strict=strict,
            progress=report,
        )

    finally:
        bar.empty()

    meta = result.pop("meta")
    record_bulk_metrics("factory_structure", time.perf_counter() - started, meta["usage"])
    st.session_state["factory_structure_meta"] = meta

    return result


def run_structured_agent(stage: str, role: str, payload: str):
    registry = get_agent_registry()
    agent = registry.get(role)

    started = time.perf_counter()
    result = agent.generate_structured(user_prompt=payload)
    elapsed = time.perf_counter() - started

    record_metrics(stage, elapsed, agent)
    return result


def run_text_agent(stage: str, role: str, payload: str) -> str:
    registry = get_agent_registry()
    agent = registry.get(role)

    started = time.perf_counter()
    result = agent.generate_response(user_prompt=payload)
    elapsed = time.perf_counter() - started

    record_metrics(stage, elapsed, agent)
    return result


def render_json_result(stage: str, label: str, data: dict) -> None:
    st.success(f"{label} selesai dalam {st.session_state['timings'].get(stage, 0):.1f} detik")

    usage = st.session_state["usages"].get(stage)
    if usage:
        columns = st.columns(3)
        columns[0].metric("Prompt tokens", usage.get("prompt_tokens") or 0)
        columns[1].metric("Completion tokens", usage.get("completion_tokens") or 0)
        columns[2].metric("Total tokens", usage.get("total_tokens") or 0)

    st.json(data, expanded=False)
    st.download_button(
        label=f"Unduh {label} (.json)",
        data=json.dumps(data, indent=2, ensure_ascii=False),
        file_name=f"{stage}.json",
        mime="application/json",
        key=f"download_{stage}",
    )


def render_sidebar():
    settings = get_agent_settings()

    st.sidebar.header("Konfigurasi")
    st.sidebar.text(f"LLM: {settings.LLM_BRIDGE_URL}")
    st.sidebar.text(f"Model: {settings.LLM_SERVED_MODEL_NAME}")
    st.sidebar.text(f"Config dir: {settings.AGENT_CONFIG_DIR}")
    st.sidebar.text(f"Schema dir: {settings.AGENT_SCHEMA_DIR}")

    st.sidebar.divider()
    st.sidebar.subheader("Pipeline paralel")

    with st.sidebar.expander("Jalankan Agent A + B bersamaan"):
        chunk_stage = st.slider("Tahap per shard", 1, 6, 3, key="ab_chunk_stage")
        chunk_wide = st.slider("Aset/job per shard", 1, 8, 4, key="ab_chunk_wide")
        shard_workers = st.slider("Shard paralel", 1, 16, 8, key="ab_shard_workers")
        cv_workers = st.slider("CV paralel", 1, 16, 12, key="ab_cv_workers")
        max_attempts = st.slider("Percobaan", 1, 5, 3, key="ab_attempts")

        if st.button("Jalankan A + B"):
            try:
                run_stage_ab_concurrently(
                    chunk_stage, chunk_wide, shard_workers, cv_workers, max_attempts
                )

            except Exception as error:
                st.sidebar.error(f"Gagal: {type(error).__name__}: {error}")
                return

            st.rerun()

    st.sidebar.divider()
    st.sidebar.subheader("Agent terdaftar")

    try:
        registry = get_agent_registry()
        roles = registry.list_roles()
        for role in roles:
            marker = "dimuat" if registry.is_loaded(role) else "belum dimuat"
            st.sidebar.text(f"{role} — {marker}")

    except Exception as error:
        st.sidebar.error(f"Registry gagal dimuat: {error}")

    st.sidebar.divider()
    if st.sidebar.button("Reset seluruh state"):
        for key in STAGE_KEYS:
            st.session_state[key] = None
        st.session_state["timings"] = {}
        st.session_state["usages"] = {}
        st.rerun()

STAGE_KEY_ALIASES = ("stage_id", "workflow_step")


def job_stage_id(job: dict) -> str | None:
    for key in STAGE_KEY_ALIASES:
        value = job.get(key)
        if value:
            return str(value)
    return None


def index_stages(twin: dict) -> dict[str, dict]:
    stages = twin.get("process_stages") or []
    return {stage["stage_id"]: stage for stage in stages if stage.get("stage_id")}


def stage_ids_for_asset(twin: dict, asset_id: str) -> list[str]:
    stages = twin.get("process_stages") or []
    return [stage["stage_id"] for stage in stages if stage.get("asset_id") == asset_id]


def quantity_text(value) -> str:
    if isinstance(value, dict):
        raw = value.get("raw")
        if raw:
            return str(raw)
        number = value.get("value")
        if number is None:
            return "-"
        unit = value.get("unit") or ""
        basis = value.get("basis")
        rendered = f"{number:g} {unit}".strip()
        return f"{rendered}/{basis}" if basis else rendered
    if value is None:
        return "-"
    return str(value)


def normalize_twin_for_legacy(twin: dict) -> dict:
    normalized = copy.deepcopy(twin)
    stages = index_stages(normalized)

    for job in read_jobs(normalized):
        stage_id = job_stage_id(job)
        if stage_id and not job.get("workflow_step"):
            job["workflow_step"] = stage_id
        if stage_id and not job.get("assigned_asset_id"):
            stage = stages.get(stage_id) or {}
            if stage.get("asset_id"):
                job["assigned_asset_id"] = stage["asset_id"]

    for asset in normalized.get("assets") or []:
        asset_id = asset.get("asset_id")
        if not asset_id or asset.get("workflow_step"):
            continue
        owners = stage_ids_for_asset(normalized, asset_id)
        if owners:
            asset["workflow_step"] = owners[0]

    return normalized


def audit_twin_for_compatibility(twin: dict) -> list[dict]:
    problems = []
    assets = {asset.get("asset_id") for asset in twin.get("assets") or []}
    stages = index_stages(twin)
    jobs = read_jobs(twin)

    if not jobs:
        return [{"job_id": "-", "masalah": "Struktur pabrik tidak memuat job_descriptions."}]

    for job in jobs:
        job_id = job.get("job_id") or job.get("allocation_id") or "(tanpa job_id)"
        stage_id = job_stage_id(job)

        if not stage_id:
            problems.append({"job_id": job_id, "masalah": "Tidak ada stage_id maupun workflow_step."})
        elif stages and stage_id not in stages:
            problems.append({"job_id": job_id, "masalah": f"stage_id '{stage_id}' tidak ada di process_stages."})

        asset_id = job.get("assigned_asset_id")

        if not asset_id:
            problems.append({"job_id": job_id, "masalah": "assigned_asset_id kosong."})
        elif asset_id not in assets:
            problems.append({"job_id": job_id, "masalah": f"assigned_asset_id '{asset_id}' tidak ada di assets."})

        if not job.get("demands"):
            problems.append({"job_id": job_id, "masalah": "Blok demands kosong."})

    return problems


def is_stage_automated(stage: dict, asset: dict) -> bool:
    for source in (stage.get("automation_level"), asset.get("automation_level")):
        token = str(source or "").strip().lower().replace(" ", "_")
        if token in AUTOMATED_TOKENS:
            return True
    return False


def stage_capacity_per_hour(stage: dict) -> float:
    direct = stage.get("throughput_per_hour")
    if direct:
        return float(direct)

    throughput = stage.get("throughput")
    if isinstance(throughput, dict) and throughput.get("value"):
        return float(throughput["value"])

    cycle = stage.get("cycle_time_seconds")
    if cycle:
        return 3600.0 / float(cycle)

    return 1.0


def jobs_grouped_by_stage(twin: dict) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for job in read_jobs(twin):
        stage_id = job_stage_id(job)
        if stage_id:
            grouped.setdefault(stage_id, []).append(job)
    return grouped


def shift_duration_hours(twin: dict) -> float:
    for shift in twin.get("shifts") or []:
        duration = shift.get("duration_hours")
        if duration:
            return float(duration)
    return 8.0


def adapt_twin_for_snapshot(twin: dict) -> dict:
    stages = twin.get("process_stages") or []
    assets = {item["asset_id"]: item for item in twin.get("assets") or [] if item.get("asset_id")}
    grouped = jobs_grouped_by_stage(twin)

    sharing: dict[str, int] = {}
    for stage in stages:
        asset_id = stage.get("asset_id")
        if asset_id:
            sharing[asset_id] = sharing.get(asset_id, 0) + 1

    sequence = []
    adapted_assets = []
    adapted_jobs = []

    for position, stage in enumerate(stages):
        stage_id = stage.get("stage_id")
        if not stage_id:
            continue

        sequence.append(stage_id)
        asset = assets.get(stage.get("asset_id")) or {}
        environment = asset.get("environmental_factors") or {}
        divisor = max(sharing.get(stage.get("asset_id"), 1), 1)

        adapted_assets.append(
            {
                "asset_id": asset.get("asset_id") or f"ast-{position + 1:02d}",
                "asset_name": asset.get("asset_name") or stage.get("stage_name") or stage_id,
                "category": asset.get("category") or "manual_station",
                "workflow_step": stage_id,
                "is_automated": is_stage_automated(stage, asset),
                "units_available": 1,
                "base_throughput_capacity": int(max(1, round(stage_capacity_per_hour(stage)))),
                "operational_cost_per_hour": float(asset.get("operational_cost_per_hour") or 0.0) / divisor,
                "environmental_factors": {
                    "noise_level_db": int(environment.get("noise_level_db") or 45),
                    "vibration_hazard_level": environment.get("vibration_hazard_level") or "low",
                    "physical_strain_index": float(environment.get("physical_strain_index") or 0.2),
                },
                "metric_derivation_reasoning": "",
            }
        )

        allocations = grouped.get(stage_id) or []
        primary = allocations[0] if allocations else {}

        headcount = 0
        for job in allocations:
            identifiers = job.get("assigned_worker_ids") or job.get("assigned_worker_names") or []
            headcount += int(job.get("headcount") or len(identifiers) or 0)

        headcount = max(1, headcount)
        demands = dict(DEFAULT_DEMANDS)
        demands.update(primary.get("demands") or {})

        adapted_jobs.append(
            {
                "job_id": primary.get("job_id") or f"job-{position + 1:02d}",
                "job_title": primary.get("job_title") or stage.get("stage_name") or stage_id,
                "workflow_step": stage_id,
                "assigned_asset_id": adapted_assets[-1]["asset_id"],
                "assigned_worker_name": [f"slot-{index + 1}" for index in range(headcount)],
                "demands": demands,
                "qc_requirement": primary.get("qc_requirement") or stage.get("qc_requirement") or "",
                "metric_derivation_reasoning": "",
            }
        )

    return {
        "factory_info": {
            "factory_id": (twin.get("factory_info") or {}).get("factory_id", "fac-unknown"),
            "factory_name": (twin.get("factory_info") or {}).get("factory_name", "-"),
            "workflow_sequence": sequence,
        },
        "assets": adapted_assets,
        "job_descriptions": adapted_jobs,
    }


def adapt_compatibility_records(adapted: dict, floor: dict, matrix: dict) -> list[dict]:
    canonical = {job["workflow_step"]: job for job in adapted["job_descriptions"]}
    by_job_id = {job["job_id"]: job for job in adapted["job_descriptions"]}

    records = []
    seen = set()

    def append(worker_id, job, evaluations, reasoning):
        key = (worker_id, job["workflow_step"])
        if key in seen:
            return
        seen.add(key)
        merged = dict(DEFAULT_EVALUATIONS)
        merged.update({name: value for name, value in (evaluations or {}).items() if name in merged})
        records.append(
            {
                "worker_id": worker_id,
                "job_id": job["job_id"],
                "asset_id": job["assigned_asset_id"],
                "evaluations": merged,
                "llm_reasoning": reasoning or "",
            }
        )

    for worker_id, record in ((matrix or {}).get("compatibility_matrix") or {}).items():
        for job_id, entry in (record.get("jobs") or {}).items():
            stage_id = entry.get("stage_id") or entry.get("workflow_step")
            job = canonical.get(stage_id) or by_job_id.get(job_id)
            if job is not None:
                append(worker_id, job, entry.get("evaluations"), entry.get("llm_reasoning"))

    for entry in (floor or {}).get("llm_compatibility_and_evaluations") or []:
        job = canonical.get(entry.get("stage_id")) or by_job_id.get(entry.get("job_id"))
        if job is not None:
            append(entry.get("worker_id"), job, entry.get("evaluations"), entry.get("llm_reasoning"))

    return records


def build_snapshot_from_session(allow_ordinal: bool = True):
    twin = st.session_state.get("factory_structure")
    floor = st.session_state.get("floor_state")
    workers = st.session_state.get("worker_profile")
    simulation = st.session_state.get("simulation_state")
    matrix = st.session_state.get("compatibility_matrix")

    normalized_floor, report = normalize_floor_state(twin, floor, allow_ordinal=allow_ordinal)

    st.session_state["floor_state"] = normalized_floor
    st.session_state["floor_alignment_report"] = report
    st.session_state["env_snapshot"] = None

    adapted = adapt_twin_for_snapshot(twin)
    records = adapt_compatibility_records(adapted, normalized_floor, matrix)

    return SnapshotBuilder(
        factory=adapted,
        floor_state=normalized_floor,
        compatibility_records=records,
        workers=(workers or {}).get("workers") or [],
        simulation_state=(simulation or {}).get("live_simulation_state") or {},
    ).build()


def render_alignment_report(report: dict) -> None:
    columns = st.columns(3)
    columns[0].metric("Posisi terbaca", report["total"])
    columns[1].metric("Terpetakan", report["resolved"])
    columns[2].metric("Tahap kosong", len(report["empty_stages"]))

    low_confidence = report["sources"].get("ordinal", 0)

    if low_confidence:
        st.warning(
            f"{low_confidence} posisi dipetakan lewat urutan workflow, bukan id eksplisit. "
            "Agent C kemungkinan tidak memakai stage_id dari process_stages."
        )

    if report["unresolved"]:
        st.error("Posisi berikut tidak bisa dipetakan dan dikeluarkan dari snapshot.")
        st.dataframe(pd.DataFrame(report["unresolved"]), use_container_width=True)

    if report["empty_stages"]:
        st.info(f"Tahap tanpa pekerja: {', '.join(report['empty_stages'])}")

    with st.expander("Sumber pemetaan stage_id"):
        st.json(report["sources"])


@st.cache_data
def load_agent_schema(name: str) -> dict:
    settings = get_agent_settings()
    return json.loads((Path(settings.schema_dir) / name).read_text(encoding="utf-8"))


def load_master_schema() -> dict:
    return load_agent_schema("factory_md.schema.json")


class StreamlitProgressCallback(BaseCallback):
    def __init__(self, total_timesteps, progress_bar, status_slot, update_every=2048):
        super().__init__(verbose=0)
        self.total_timesteps = total_timesteps
        self.progress_bar = progress_bar
        self.status_slot = status_slot
        self.update_every = update_every
        self.started = time.perf_counter()

    def _on_step(self) -> bool:
        if self.num_timesteps % self.update_every != 0:
            return True

        fraction = min(1.0, self.num_timesteps / max(self.total_timesteps, 1))
        elapsed = time.perf_counter() - self.started
        speed = self.num_timesteps / max(elapsed, 1e-6)
        remaining = (self.total_timesteps - self.num_timesteps) / max(speed, 1e-6)

        self.progress_bar.progress(fraction)
        self.status_slot.text(
            f"{self.num_timesteps:,}/{self.total_timesteps:,} langkah — "
            f"{speed:,.0f} langkah/detik — sisa sekitar {remaining:.0f} detik"
        )
        return True


def build_training_env(snapshot, scenario, config):
    def initializer():
        env = FactoryOptimizationEnv(
            snapshot=snapshot,
            scenario=scenario,
            params=HumanFactorsParams(),
            sample_weights=True,
            randomize_start=True,
            seed=config.seed,
        )
        return Monitor(ActionMasker(env, mask_function))

    vector = DummyVecEnv([initializer for _ in range(config.n_envs)])
    return VecNormalize(
        vector,
        training=True,
        norm_obs=False,
        norm_reward=True,
        clip_reward=10.0,
        gamma=config.gamma,
    )


def heuristic_action(env) -> np.ndarray:
    masks = env.action_masks()
    span = env.n_stations + 2
    assignment_mask = masks[: env.assignment_actions]
    counts = env._headcount()

    noop = env.n_workers * span
    best_action = noop
    best_score = 0.05

    for action in np.flatnonzero(assignment_mask):
        worker, target = divmod(int(action), span)

        if worker >= env.n_workers:
            continue

        origin = int(env.assignment[worker])
        fatigue = float(env.fatigue[worker])

        if target == env.n_stations:
            score = 2.0 * max(0.0, fatigue - 0.70)
        elif target < env.n_stations:
            gain = float(env.compatibility[worker, target, 0])
            if origin >= 0:
                gain -= float(env.compatibility[worker, origin, 0])

            relief = 1.0 - counts[target] / max(float(env.max_headcount[target]), 1.0)
            strain_cost = float(env.strain[target]) * max(0.0, fatigue - 0.55)
            score = gain + 0.5 * relief - 1.5 * strain_cost
        else:
            continue

        if score > best_score:
            best_score = score
            best_action = int(action)

    return np.array([best_action, 0], dtype=np.int64)


def heuristic_rollout(snapshot, scenario, weights, seed=42) -> dict:
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
        observation, reward, terminated, truncated, info = env.step(heuristic_action(env))
        total_reward += reward

    info["episode_reward"] = total_reward
    env.close()
    return info


def attach_deltas(payload: dict) -> dict:
    for key in (
        "throughput_per_hour",
        "human_error_rate_pct",
        "total_op_cost_per_hour_rp",
        "cost_per_item_rp",
    ):
        before = payload["metrics"][key].get("before", 0.0)
        after = payload["metrics"][key]["after"]
        delta = 0.0 if abs(before) < 1e-9 else (after - before) / abs(before) * 100.0
        payload["metrics"][key]["delta_pct"] = round(delta, 2)
        payload["metrics"][key]["direction"] = "up" if delta > 0 else "down" if delta < 0 else "flat"
    return payload


def render_snapshot_summary(snapshot) -> None:
    summary = snapshot.summary()

    columns = st.columns(4)
    columns[0].metric("Pekerja (N)", summary["n_workers"])
    columns[1].metric("Stasiun (M)", summary["n_stations"])
    columns[2].metric("Dimensi observasi", summary["observation_dim"])
    columns[3].metric("Bit mask aksi", summary["mask_bits"])

    columns = st.columns(4)
    columns[0].metric("Target laju lini", f"{summary['target_line_rate']:,.0f}/jam")
    columns[1].metric("Baseline throughput", f"{summary['baseline_throughput']:,.1f}/jam")
    columns[2].metric("Baseline error", f"{summary['baseline_error_rate'] * 100:.2f}%")
    columns[3].metric("Baseline biaya/item", f"Rp{summary['baseline_cost_per_item']:,.0f}")

    st.dataframe(
        pd.DataFrame(
            {
                "stage_id": list(snapshot.maps.station_ids),
                "kapasitas_per_jam": snapshot.station_capacity,
                "min_pekerja": snapshot.constraints.min_headcount,
                "max_pekerja": snapshot.constraints.max_headcount,
                "biaya_per_jam": snapshot.asset_cost_per_hour,
            }
        ),
        use_container_width=True,
    )


def render_weight_controls() -> RewardWeights:
    preset = WEIGHT_PRESETS[st.selectbox("Preset prioritas manajer", list(WEIGHT_PRESETS.keys()))]

    columns = st.columns(4)
    throughput = columns[0].slider("Throughput", 0.0, 1.0, preset[0], 0.05)
    cost = columns[1].slider("Biaya", 0.0, 1.0, preset[1], 0.05)
    fatigue = columns[2].slider("Kelelahan", 0.0, 1.0, preset[2], 0.05)
    bottleneck = columns[3].slider("Bottleneck", 0.0, 1.0, preset[3], 0.05)

    return RewardWeights.from_vector(
        np.array([throughput, cost, fatigue, bottleneck], dtype=np.float32)
    )


def render_scenario_detail(payload: dict) -> None:
    metrics = payload["metrics"]

    columns = st.columns(4)
    columns[0].metric(
        "Throughput/jam",
        f"{metrics['throughput_per_hour']['after']:,.1f}",
        f"{metrics['throughput_per_hour'].get('delta_pct', 0):+.1f}%",
    )
    columns[1].metric(
        "Error rate",
        f"{metrics['human_error_rate_pct']['after']:.2f}%",
        f"{metrics['human_error_rate_pct'].get('delta_pct', 0):+.1f}%",
        delta_color="inverse",
    )
    columns[2].metric(
        "Biaya per item",
        f"Rp{metrics['cost_per_item_rp']['after']:,.0f}",
        f"{metrics['cost_per_item_rp'].get('delta_pct', 0):+.1f}%",
        delta_color="inverse",
    )
    columns[3].metric("Bottleneck tersisa", metrics["bottleneck_count"]["after"])

    columns = st.columns(3)
    columns[0].metric("Kelelahan rata-rata", f"{metrics['mean_fatigue']['after']:.3f}")
    columns[1].metric("Kelelahan tertinggi", f"{metrics['max_fatigue']['after']:.3f}")
    columns[2].metric("Capex terpakai", f"Rp{payload['constraints']['capex_used_rp']:,.0f}")

    flow = payload["factory_flow_optimal"]

    st.markdown("**Posisi optimal seluruh pekerja**")
    st.dataframe(pd.DataFrame(flow["optimal_staff_positions"]), use_container_width=True)

    if flow["reallocation_moves"]:
        st.markdown("**Rekomendasi perpindahan**")
        st.dataframe(pd.DataFrame(flow["reallocation_moves"]), use_container_width=True)
    else:
        st.info("Kebijakan tidak merekomendasikan perpindahan pekerja pada bobot ini.")

    if flow["asset_upgrades"]:
        st.markdown("**Upgrade aset**")
        st.dataframe(pd.DataFrame(flow["asset_upgrades"]), use_container_width=True)

    if flow["new_hires"]:
        st.markdown("**Rekrutmen baru**")
        st.dataframe(pd.DataFrame(flow["new_hires"]), use_container_width=True)

    if flow["residual_bottleneck"]:
        st.warning(f"Bottleneck tersisa: {flow['residual_bottleneck']}")


def run_stage_ab_concurrently(chunk_stage: int, chunk_wide: int, shard_workers: int,
                              cv_workers: int, max_attempts: int) -> None:
    payload = st.session_state["agent_input"]
    document = st.session_state["worker_document"]
    workbook = st.session_state.get("workbook_dict")
    stage_names = st.session_state.get("stage_names")

    if not payload or document is None:
        st.sidebar.warning("Butuh payload pabrik (tab 1) dan dokumen CV (tab 4).")
        return

    registry = get_agent_registry()
    structure_agent = registry.get(AgentRole.FACTORY_STRUCTURE)
    profile_agent = registry.get(AgentRole.WORKER_PROFILE)
    master_schema = load_master_schema()

    def stage_a() -> tuple[dict, float]:
        started = time.perf_counter()
        result = generate_factory_structure(
            agent=structure_agent,
            master_schema=master_schema,
            payload=payload,
            workbook=workbook,
            stage_names=stage_names,
            chunk_sizes={
                "process_stages": chunk_stage,
                "assets": chunk_wide,
                "job_descriptions": chunk_wide,
            },
            max_workers=shard_workers,
            max_attempts=max_attempts,
        )
        return result, time.perf_counter() - started

    def stage_b() -> tuple[dict, float]:
        started = time.perf_counter()
        result = generate_worker_profiles(
            document=document,
            agent=profile_agent,
            candidate_payload=candidate_payload,
            max_workers=cv_workers,
            max_attempts=max_attempts,
            strict=False,
        )
        return result, time.perf_counter() - started

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(stage_a)
        future_b = pool.submit(stage_b)

        structure, elapsed_a = future_a.result()
        profiles, elapsed_b = future_b.result()

    meta = structure.pop("meta")
    st.session_state["factory_structure"] = structure
    st.session_state["factory_structure_meta"] = meta
    st.session_state["worker_profile"] = profiles

    record_bulk_metrics("factory_structure", elapsed_a, meta["usage"])
    record_bulk_metrics("worker_profile", elapsed_b, profiles["meta"].get("usage"))

    st.sidebar.success(
        f"Agent A {elapsed_a:.1f}s, Agent B {elapsed_b:.1f}s, "
        f"dinding {max(elapsed_a, elapsed_b):.1f}s."
    )


def tab_extraction():
    st.subheader("Tahap 1 — Ekstraksi workbook")

    uploaded = st.file_uploader("Workbook pabrik", type=["xlsx", "xlsm", "pdf", "docx", "md"])

    if uploaded is not None and st.button("Ekstrak"):
        saved_path = persist_upload(uploaded)

        with st.spinner("Extracting documents..."):
            started = time.perf_counter()

            try:
                # Extract all supported types (including excel)
                source = extract_any(saved_path)

            except (UnsupportedDocumentError, UnsupportedWorkbookError) as error:
                st.error(str(error))
                return

            elapsed = time.perf_counter() - started

        st.success(f"Extraction done at {elapsed:.2f} seconds")
        st.session_state["extracted_source"] = source
        st.session_state["agent_input"] = build_any_agent_input(source)

        if is_workbook(saved_path):
            st.session_state["validation_report"] = validate_workbook(source)
            st.session_state["workbook_dict"] = workbook_as_dict(source)
            st.session_state["stage_names"] = None
        else:
            st.session_state["workbook_dict"] = None
            st.session_state["stage_names"] = (
                source.workflow_sequence() if hasattr(source, "workflow_sequence") else None
            )


def tab_validation():
    st.subheader("Tahap 2 — Validasi integritas data")

    report = st.session_state.get("validation_report")

    if report is None:
        st.info("Belum ada workbook yang divalidasi.")
        return

    columns = st.columns(3)
    columns[0].metric("Status", "Lolos" if report.is_complete else "Perlu perbaikan")
    columns[1].metric("Blocking", report.blocking_count)
    columns[2].metric("Warning", report.warning_count)

    if report.issues:
        st.dataframe(pd.DataFrame(report.as_records()), use_container_width=True)

    if report.is_complete:
        st.success("Data konsisten. Pipeline boleh dilanjutkan ke Agent A.")
        return

    st.error("Agent A diblokir sampai temuan blocking diperbaiki.")

    if st.button("Susun pertanyaan perbaikan"):
        text = run_text_agent(
            stage="data_repair",
            role=AgentRole.DATA_REPAIR,
            payload=report.as_prompt_payload(),
        )
        st.session_state["clarification_text"] = text

    if st.session_state.get("clarification_text"):
        st.info(st.session_state["clarification_text"])

    repairs_json = st.text_area("Blok PERBAIKAN dari chatbot", height=160, key="repairs_json")

    if repairs_json and st.button("Terapkan perbaikan"):
        source = st.session_state["extracted_source"]
        raw, rejected = apply_repairs(source.raw, json.loads(repairs_json))

        if rejected:
            st.warning(f"Alamat tidak dikenali: {', '.join(rejected)}")

        repaired = build_workbook(raw)
        st.session_state["extracted_source"] = repaired
        st.session_state["agent_input"] = build_workbook_agent_input(repaired)
        st.session_state["validation_report"] = validate_workbook(repaired)
        st.rerun()


def tab_structure():
    st.subheader("Tahap 2 — Agent A: struktur pabrik")

    payload = st.session_state["agent_input"]

    if not payload:
        st.info("Selesaikan tahap ekstraksi terlebih dahulu.")
        return

    parallel = st.toggle("Mode shard paralel", value=True)

    if parallel:
        columns = st.columns(5)
        chunk_stage = columns[0].slider("Tahap per shard", 1, 6, 3)
        chunk_wide = columns[1].slider("Aset/job per shard", 1, 8, 4)
        max_workers = columns[2].slider("Shard paralel", 1, 16, 8)
        max_attempts = columns[3].slider("Percobaan per shard", 1, 5, 3)
        shard_timeout_min = columns[4].slider("Batas waktu per shard (menit)", 2, 20, 8)
        strict = st.checkbox("Hentikan bila ada shard gagal", value=False)

    if st.button("Jalankan factory_structure_agent"):
        try:
            if parallel:
                result = run_factory_structure_parallel(
                    payload, chunk_stage, chunk_wide, max_workers, max_attempts,
                    shard_timeout_min, strict
                )
            else:
                with st.spinner("Menghubungi vLLM..."):
                    result = run_structured_agent(
                        stage="factory_structure",
                        role=AgentRole.FACTORY_STRUCTURE,
                        payload=payload,
                    )

            st.session_state["factory_structure"] = result

        except LLMOutputTruncatedError as error:
            st.error(
                f"{error} Pabrik ini kemungkinan terlalu besar untuk satu completion. "
                "Aktifkan 'Mode shard paralel' di atas — itu memecah struktur menjadi "
                "potongan kecil dan tidak akan terpotong."
            )
            return

        except ShardGenerationError as error:
            st.error(str(error))
            st.dataframe(pd.DataFrame(error.failures), use_container_width=True)
            return

        except Exception as error:
            st.error(f"Agent gagal: {type(error).__name__}: {error}")
            return

    meta = st.session_state.get("factory_structure_meta")

    if meta:
        columns = st.columns(4)
        columns[0].metric("Shard", meta["shard_count"])
        columns[1].metric("Shard gagal", meta["shard_failed"])
        columns[2].metric("Percobaan ulang", meta["retries"])
        columns[3].metric("Detik", meta["elapsed_seconds"])

        if meta["cross_reference_problems"]:
            st.warning("Hasil gabungan memuat referensi silang yang tidak konsisten.")
            st.dataframe(pd.DataFrame(meta["cross_reference_problems"]), use_container_width=True)

    twin = st.session_state["factory_structure"]

    if twin is None:
        return

    render_json_result("factory_structure", "Struktur pabrik", twin)

    info = twin.get("factory_info", {})
    columns = st.columns(5)
    columns[0].metric("Tahapan", len(twin.get("process_stages") or []))
    columns[1].metric("Aset", len(twin.get("assets", [])))
    columns[2].metric("Job desk", len(read_jobs(twin)))
    columns[3].metric("Shift", len(twin.get("shifts") or []))
    columns[4].metric("Jenis proses", info.get("process_type", "-"))

    lanes = info.get("lanes") or []
    groups = info.get("parallel_groups") or []

    if lanes or groups:
        st.markdown("**Struktur alur**")
        st.write(f"Urutan topologis: {' -> '.join(info.get('workflow_sequence') or []) or '-'}")
        st.write(f"Jalur paralel: {', '.join(lanes) or '-'}")

        for group in groups:
            target = group.get("converges_to") or "FINISHED"
            st.write(f"{group.get('group_id')}: {', '.join(group.get('steps', []))} menyatu di {target}")

    stage_rows = []
    for stage in twin.get("process_stages") or []:
        stage_rows.append(
            {
                "stage_id": stage.get("stage_id"),
                "tahapan": stage.get("stage_name"),
                "jalur": stage.get("lane"),
                "berikutnya": "FINISHED" if stage.get("is_terminal") else stage.get("next_stage_id"),
                "aset": stage.get("asset_id"),
                "aliran": stage.get("flow_type"),
                "siklus_detik": stage.get("cycle_time_seconds"),
                "throughput": quantity_text(stage.get("throughput")),
                "per_jam": stage.get("throughput_per_hour"),
                "otomatisasi": stage.get("automation_level"),
            }
        )

    if stage_rows:
        st.markdown("**Ringkasan tahapan proses**")
        st.dataframe(pd.DataFrame(stage_rows), use_container_width=True)

    asset_rows = []
    for asset in twin.get("assets", []):
        environment = asset.get("environmental_factors") or {}
        asset_rows.append(
            {
                "asset_id": asset.get("asset_id"),
                "nama": asset.get("asset_name"),
                "kategori": asset.get("category"),
                "tahapan": ", ".join(stage_ids_for_asset(twin, asset.get("asset_id"))) or "-",
                "otomatisasi": asset.get("automation_level"),
                "unit": asset.get("units_available"),
                "kapasitas_unit": quantity_text(asset.get("capacity_per_unit")),
                "kapasitas_total": quantity_text(asset.get("total_capacity")),
                "biaya_per_jam": asset.get("operational_cost_per_hour"),
                "daya_watt": environment.get("power_consumption_watt"),
                "bising_db": environment.get("noise_level_db"),
                "strain": environment.get("physical_strain_index"),
            }
        )

    if asset_rows:
        st.markdown("**Ringkasan aset**")
        st.dataframe(pd.DataFrame(asset_rows), use_container_width=True)

    stages = index_stages(twin)
    job_rows = []

    for job in read_jobs(twin):
        demands = job.get("demands", {})
        stage_id = job_stage_id(job)
        stage = stages.get(stage_id or "", {})
        assigned = job.get("assigned_worker_ids") or job.get("assigned_worker_names") or []
        job_rows.append(
            {
                "job_id": job.get("job_id"),
                "alokasi": job.get("allocation_id"),
                "judul": job.get("job_title"),
                "stage_id": stage_id,
                "tahapan": stage.get("stage_name"),
                "aset": job.get("assigned_asset_id"),
                "shift": job.get("shift_id"),
                "jumlah": job.get("headcount"),
                "pekerja": ", ".join(str(item) for item in assigned) or "-",
                "fokus": demands.get("required_cognitive_focus"),
                "fisik": demands.get("physical_demand_level"),
                "severity": demands.get("error_severity"),
            }
        )

    if job_rows:
        st.markdown("**Ringkasan job desk**")
        st.dataframe(pd.DataFrame(job_rows), use_container_width=True)

    shift_rows = []
    for shift in twin.get("shifts") or []:
        shift_rows.append(
            {
                "shift_id": shift.get("shift_id"),
                "mulai": shift.get("start_time"),
                "selesai": shift.get("end_time"),
                "durasi_jam": shift.get("duration_hours"),
                "lintas_tengah_malam": shift.get("crosses_midnight"),
            }
        )

    if shift_rows:
        st.markdown("**Ringkasan shift**")
        st.dataframe(pd.DataFrame(shift_rows), use_container_width=True)


def tab_completeness():
    st.subheader("Tahap 3 — Pemeriksaan kelengkapan")

    twin = st.session_state["factory_structure"]

    manual_json = st.text_area(
        "Atau tempel JSON digital twin langsung untuk diuji",
        height=180,
        key="manual_twin_json",
    )

    if st.button("Periksa JSON tempelan"):
        if not manual_json.strip():
            st.warning("Tempel JSON terlebih dahulu sebelum menekan tombol ini.")
        else:
            try:
                twin = json.loads(manual_json)
                st.session_state["factory_structure"] = twin
                st.toast(f"JSON diterima ({len(manual_json)} karakter, {len(twin)} key tingkat atas).")

            except json.JSONDecodeError as error:
                st.error(f"JSON tidak valid: {error}")
                return

    if twin is None:
        st.info("Belum ada struktur pabrik untuk diperiksa. Jalankan Agent A atau tempel JSON di atas.")
        return

    try:
        report = check_factory_completeness(twin)

    except Exception as error:
        st.error(f"Pemeriksaan kelengkapan gagal: {type(error).__name__}: {error}")
        st.exception(error)
        return

    st.session_state["completeness_report"] = report

    columns = st.columns(3)
    columns[0].metric("Status", "Lengkap" if report.is_complete else "Belum lengkap")
    columns[1].metric("Blocking", report.blocking_count)
    columns[2].metric("Warning", report.warning_count)

    if not report.gaps:
        st.success("Tidak ada field yang kurang.")
        return

    gap_rows = [
        {
            "severity": str(gap.severity),
            "path": gap.path,
            "masalah": gap.message,
            "pertanyaan": gap.question,
        }
        for gap in report.gaps
    ]

    frame = pd.DataFrame(gap_rows)
    blocking_frame = frame[frame["severity"] == GapSeverity.BLOCKING.value]
    warning_frame = frame[frame["severity"] == GapSeverity.WARNING.value]

    if not blocking_frame.empty:
        st.markdown("**Blocking**")
        st.dataframe(blocking_frame, use_container_width=True)

    if not warning_frame.empty:
        st.markdown("**Warning**")
        st.dataframe(warning_frame, use_container_width=True)

    st.divider()

    if st.button("Susun pertanyaan klarifikasi ke user"):
        with st.spinner("Menyusun pertanyaan..."):
            try:
                text = run_text_agent(
                    stage="clarification",
                    role=AgentRole.FACTORY_CLARIFICATION,
                    payload=report.as_prompt_payload(),
                )
                st.session_state["clarification_text"] = text

            except Exception as error:
                st.error(f"Agent klarifikasi gagal: {error}")

    if st.session_state["clarification_text"]:
        st.markdown("**Pertanyaan untuk user**")
        st.info(st.session_state["clarification_text"])


def tab_worker_extraction():
    st.subheader("Tahap 4 — Ekstraksi CV / wawancara dan Agent B")

    uploaded = st.file_uploader(
        "Berkas CV (ATS), catatan wawancara, atau arsip ZIP berisi banyak CV",
        type=["zip", "pdf", "docx", "md", "markdown", "txt"],
        accept_multiple_files=True,
        key="worker_uploader",
    )

    st.caption(
        "Arsip ZIP boleh memuat campuran PDF dan Markdown, termasuk di dalam subfolder. "
        "Berkas sistem, ekstensi tidak didukung, dan jalur tidak aman akan dilewati."
    )

    strict = st.checkbox("Hentikan proses bila ada berkas gagal diekstraksi", value=False)

    if uploaded and st.button("Ekstrak dokumen pekerja"):
        saved_paths = [persist_upload(item) for item in uploaded]

        bar = st.progress(0.0, text="Menyiapkan berkas...")

        def report(done: int, total: int) -> None:
            bar.progress(done / total, text=f"Memproses berkas {done}/{total}")

        try:
            document, archive_reports = extract_worker_uploads(
                saved_paths,
                strict=strict,
                progress=report,
            )

        except ArchiveError as error:
            bar.empty()
            st.error(str(error))
            return

        except UnsupportedDocumentError as error:
            bar.empty()
            st.error(str(error))
            return

        except Exception as error:
            bar.empty()
            st.error(f"Ekstraksi gagal: {type(error).__name__}: {error}")
            return

        bar.empty()
        st.session_state["worker_document"] = document
        st.session_state["worker_archive_reports"] = archive_reports
        st.session_state["worker_agent_input"] = build_worker_agent_input(document)

    for archive_report in st.session_state.get("worker_archive_reports") or []:
        with st.expander(
            f"Arsip {archive_report.archive_name} — {archive_report.accepted_count()} berkas diproses"
        ):
            counts = archive_report.suffix_counts()
            if counts:
                st.caption(" · ".join(f"{suffix}: {total}" for suffix, total in sorted(counts.items())))

            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "member": member.member_name,
                            "berkas": member.file_name,
                            "ekstensi": member.suffix,
                            "ukuran_byte": member.size_bytes,
                        }
                        for member in archive_report.accepted
                    ]
                ),
                use_container_width=True,
            )

            if archive_report.skipped:
                st.markdown("**Dilewati**")
                st.dataframe(pd.DataFrame(archive_report.skipped), use_container_width=True)

            if archive_report.failed:
                st.markdown("**Gagal diekstraksi**")
                st.dataframe(pd.DataFrame(archive_report.failed), use_container_width=True)

    document = st.session_state["worker_document"]

    if document is not None and document.candidates:
        st.divider()
        st.caption(
            "Payload gabungan di bawah ini hanya untuk audit. Tombol di bawah mengirim "
            "satu panggilan agent terpisah per kandidat secara paralel, bukan payload gabungan ini."
        )
        st.text_area(
            "Payload gabungan (referensi)",
            value=st.session_state["worker_agent_input"] or "",
            height=200,
            disabled=True,
        )

        max_workers = st.slider("Panggilan paralel", min_value=1, max_value=16, value=6)
        max_attempts = st.slider("Percobaan per kandidat", min_value=1, max_value=5, value=3)
        strict = st.checkbox("Hentikan seluruh proses bila ada kandidat gagal", value=False)

        if st.button("Jalankan cv_to_worker_profile_creator (paralel)"):
            try:
                agent = get_agent_registry().get(AgentRole.WORKER_PROFILE)

            except Exception as error:
                st.error(f"Agent tidak tersedia: {error}")
                return

            bar = st.progress(0.0, text="Menyiapkan kandidat...")

            def report(done: int, total: int) -> None:
                bar.progress(done / total, text=f"Memproses kandidat {done}/{total}")

            started = time.perf_counter()

            try:
                result = generate_worker_profiles(
                    document=document,
                    agent=agent,
                    candidate_payload=candidate_payload,
                    max_workers=max_workers,
                    max_attempts=max_attempts,
                    strict=strict,
                    progress=report,
                )

            except WorkerProfileGenerationError as error:
                bar.empty()
                st.error(str(error))
                st.dataframe(pd.DataFrame(error.failures), use_container_width=True)
                return

            except Exception as error:
                bar.empty()
                st.error(f"Agent gagal: {type(error).__name__}: {error}")
                return

            elapsed = time.perf_counter() - started
            bar.empty()

            record_bulk_metrics("worker_profile", elapsed, result["meta"].get("usage"))
            st.session_state["worker_profile"] = result
            st.success(
                f"{result['meta']['processed_count']}/{result['meta']['candidate_count']} "
                f"kandidat selesai dalam {elapsed:.2f} detik "
                f"({result['meta']['retries']} percobaan ulang)."
            )

            if result["meta"]["failures"]:
                st.warning("Sebagian kandidat gagal dan dikeluarkan dari hasil.")
                st.dataframe(pd.DataFrame(result["meta"]["failures"]), use_container_width=True)


    workers = st.session_state["worker_profile"]

    if workers is not None:
        render_json_result("worker_profile", "Profil pekerja", workers)

        profile_rows = []
        for worker in workers.get("workers", []):
            demographics = worker.get("demographics", {})
            shift = worker.get("shift_context", {})
            profile_rows.append(
                {
                    "worker_id": worker.get("worker_id"),
                    "nama": worker.get("name"),
                    "usia": demographics.get("age"),
                    "pengalaman": demographics.get("years_of_experience"),
                    "stamina": demographics.get("baseline_physical_stamina"),
                    "resiliensi": demographics.get("cognitive_resilience"),
                    "jam_hari_ini": shift.get("hours_worked_today"),
                    "shift_beruntun": shift.get("consecutive_shifts"),
                }
            )

        if profile_rows:
            st.dataframe(pd.DataFrame(profile_rows), use_container_width=True)


def tab_compatibility():
    st.subheader("Tahap 5 — Matriks kompatibilitas pekerja x job desk")

    twin = st.session_state["factory_structure"]
    workers = st.session_state["worker_profile"]

    if twin is None:
        st.info("Butuh struktur pabrik dari Agent A terlebih dahulu.")
        return

    if workers is None:
        st.info("Butuh profil pekerja dari Agent B terlebih dahulu.")
        return

    twin = normalize_twin_for_legacy(twin)
    worker_list = workers.get("workers", [])
    job_list = read_jobs(twin)

    problems = audit_twin_for_compatibility(twin)

    if problems:
        st.warning(
            "Sebagian job desk tidak layak dievaluasi dan akan dilewati. "
            "Perbaiki dulu di tab validasi bila hasilnya harus lengkap."
        )
        st.dataframe(pd.DataFrame(problems), use_container_width=True)

    asset_ids = {asset.get("asset_id") for asset in twin.get("assets") or []}
    eligible = [job for job in job_list if job.get("assigned_asset_id") in asset_ids]

    if not eligible:
        st.error(
            "Tidak ada job desk dengan assigned_asset_id yang valid. "
            "Matriks tidak bisa dibangun."
        )
        return

    columns = st.columns(4)
    columns[0].metric("Pekerja", len(worker_list))
    columns[1].metric("Job desk", len(job_list))
    columns[2].metric("Job layak", len(eligible))
    columns[3].metric("Pasangan", len(worker_list) * len(eligible))

    max_workers = columns[2].slider("Shard paralel", min_value=1, max_value=16, value=4)
    max_attempts = st.slider("Percobaan per pasangan", min_value=1, max_value=5, value=3)
    strict = st.checkbox("Hentikan seluruh proses bila ada pasangan gagal", value=False)

    if st.button("Bangun matriks kompatibilitas"):
        try:
            agent = get_agent_registry().get(AgentRole.WORKER_COMPATIBILITY)

        except Exception as error:
            st.error(f"Agent tidak tersedia: {error}")
            return

        bar = st.progress(0.0, text="Menyiapkan pasangan...")

        def report(done: int, total: int) -> None:
            bar.progress(done / total, text=f"Evaluasi pasangan {done}/{total}")

        started = time.perf_counter()

        try:
            matrix = generate_compatibility_matrix(
                factory=twin,
                workers=worker_list,
                agent=agent,
                max_workers=max_workers,
                max_attempts=max_attempts,
                strict=strict,
                progress=report,
            )

        except CompatibilityEvaluationError as error:
            bar.empty()
            st.error(str(error))
            st.dataframe(pd.DataFrame(error.failures), use_container_width=True)
            return

        except Exception as error:
            bar.empty()
            st.error(f"Pembentukan matriks gagal: {type(error).__name__}: {error}")
            return

        st.session_state["timings"]["compatibility_matrix"] = time.perf_counter() - started
        st.session_state["compatibility_matrix"] = matrix
        bar.empty()

    matrix = st.session_state["compatibility_matrix"]

    if matrix is None:
        return

    render_json_result("compatibility_matrix", "Matriks kompatibilitas", matrix)

    meta = matrix.get("meta", {})
    columns = st.columns(3)
    columns[0].metric("Pasangan berhasil", meta.get("evaluated_pairs", 0))
    columns[1].metric("Percobaan ulang", meta.get("retries", 0))
    columns[2].metric("Pasangan gagal", len(meta.get("failed_pairs", [])))

    if meta.get("failed_pairs"):
        st.warning("Sebagian pasangan tidak berhasil dievaluasi agent dan dikeluarkan dari matriks.")
        st.dataframe(pd.DataFrame(meta["failed_pairs"]), use_container_width=True)

    flat_rows = []
    score_rows = {}

    for worker_id, record in matrix.get("compatibility_matrix", {}).items():
        score_rows[worker_id] = {}
        for job_id, entry in record.get("jobs", {}).items():
            evaluations = entry.get("evaluations", {})
            score_rows[worker_id][job_id] = evaluations.get("overall_compatibility_score")
            flat_rows.append(
                {
                    "worker_id": worker_id,
                    "nama": record.get("worker_name"),
                    "job_id": job_id,
                    "job": entry.get("job_title"),
                    "stage_id": entry.get("stage_id") or entry.get("workflow_step"),
                    "asset_id": entry.get("asset_id"),
                    "score": evaluations.get("overall_compatibility_score"),
                    "throughput": evaluations.get("throughput_multiplier"),
                    "error": evaluations.get("error_multiplier"),
                    "fatigue": evaluations.get("fatigue_accumulation_rate"),
                    "stress": evaluations.get("stress_sensitivity_factor"),
                    "attempts": entry.get("attempts"),
                    "terbaik": job_id == record.get("best_job_id"),
                }
            )

    if score_rows:
        st.markdown("**Peta skor kompatibilitas**")
        heat = pd.DataFrame(score_rows).transpose().sort_index()
        st.dataframe(heat.style.background_gradient(cmap="RdYlGn"), use_container_width=True)

    if flat_rows:
        frame = pd.DataFrame(flat_rows)

        st.markdown("**Pasangan terbaik per pekerja**")
        st.dataframe(frame[frame["terbaik"]].drop(columns=["terbaik"]), use_container_width=True)

        with st.expander("Seluruh pasangan"):
            st.dataframe(frame.drop(columns=["terbaik"]), use_container_width=True)

        selected = st.selectbox(
            "Lihat penalaran pasangan",
            options=frame.index,
            format_func=lambda index: f"{frame.loc[index, 'worker_id']} x {frame.loc[index, 'job_id']}",
        )
        worker_id = frame.loc[selected, "worker_id"]
        job_id = frame.loc[selected, "job_id"]
        st.info(matrix["compatibility_matrix"][worker_id]["jobs"][job_id]["llm_reasoning"])


def tab_downstream():
    st.subheader("Tahap 6 — Pipeline lanjutan")

    twin = st.session_state["factory_structure"]
    workers = st.session_state["worker_profile"]

    if twin is None:
        st.info("Selesaikan Agent A terlebih dahulu.")
        return

    if workers is None:
        st.info("Selesaikan Agent B pada tab pekerja terlebih dahulu.")
        return

    st.markdown("**Agent C — kondisi lantai produksi**")

    INIT_STATE_SCHEMA = load_agent_schema("init_state.schema.json")

    if st.button("Jalankan floor_state_agent"):
        payload = {
            "factory_info": twin.get("factory_info"),
            "shifts": twin.get("shifts"),
            "process_stages": twin.get("process_stages"),
            "assets": twin.get("assets"),
            "job_descriptions": read_jobs(twin),
            "workers": workers.get("workers"),
            "compatibility_matrix": (st.session_state["compatibility_matrix"] or {}).get(
                "compatibility_matrix"
            ),
        }

        with st.spinner("Menempatkan pekerja..."):
            try:
                result = run_structured_agent(
                    stage="floor_state",
                    role=AgentRole.INIT_STATE,
                    payload=json.dumps(payload, ensure_ascii=False),
                )
                validate_init_state_shape(result, INIT_STATE_SCHEMA)

                normalized, report = normalize_floor_state(twin, result)
                validate_stage_ids(normalized, twin["factory_info"]["workflow_sequence"])
                st.session_state["floor_state"] = normalized
                st.session_state["floor_alignment_report"] = report

                if report["unresolved"] or report["sources"].get("ordinal"):
                    st.warning(
                        "Sebagian stage_id dari Agent C tidak cocok dengan process_stages "
                        "dan dipetakan ulang. Lihat laporan di tab Optimasi RL."
                    )

            except FloorStateAlignmentError as error:
                st.error(f"Penempatan tidak bisa dipetakan: {error}")

            except ValueError as error:
                st.error(f"Output floor_state_agent tidak sesuai schema: {error}")

            except Exception as error:
                st.error(f"Agent gagal: {type(error).__name__}: {error}")

    floor = st.session_state["floor_state"]

    if floor is not None:
        render_json_result("floor_state", "Kondisi lantai", floor)

    st.divider()
    st.markdown("**Agent D — state simulasi**")

    if floor is None:
        st.info("Butuh output Agent C terlebih dahulu.")
        return

    if st.button("Jalankan simulation_state_agent"):
        payload = {
            "assets": twin.get("assets"),
            "process_stages": twin.get("process_stages"),
            "shifts": twin.get("shifts"),
            "job_descriptions": read_jobs(twin),
            "workers": workers.get("workers"),
            "factory_flow_rightnow": floor.get("factory_flow_rightnow"),
            "llm_compatibility_and_evaluations": floor.get("llm_compatibility_and_evaluations"),
        }

        with st.spinner("Menghitung metrik simulasi..."):
            try:
                result = run_structured_agent(
                    stage="simulation_state",
                    role=AgentRole.SIMULATION_STATE,
                    payload=json.dumps(payload, ensure_ascii=False),
                )
                st.session_state["simulation_state"] = result

            except Exception as error:
                st.error(f"Agent gagal: {error}")

    simulation = st.session_state["simulation_state"]

    if simulation is not None:
        render_json_result("simulation_state", "State simulasi", simulation)

        state = simulation.get("live_simulation_state", {})
        metric_rows = []
        for assignment in state.get("current_assignments", []):
            metrics = assignment.get("calculated_realtime_metrics", {})
            metric_rows.append(
                {
                    "worker_id": assignment.get("worker_id"),
                    "job_id": assignment.get("assigned_job_id"),
                    "fatigue": metrics.get("current_fatigue_level"),
                    "stress": metrics.get("current_stress_level"),
                    "throughput": metrics.get("effective_throughput_per_hour"),
                    "error_prob": metrics.get("effective_error_probability"),
                    "burnout": metrics.get("burnout_hazard_risk"),
                }
            )

        utilization = state.get("stage_utilization", [])
        if utilization:
            st.markdown("**Utilisasi per tahapan**")
            st.dataframe(pd.DataFrame(utilization), use_container_width=True)

        if metric_rows:
            st.dataframe(pd.DataFrame(metric_rows), use_container_width=True)

        bottlenecks = state.get("system_bottlenecks", [])
        if bottlenecks:
            st.warning(f"Bottleneck: {', '.join(bottlenecks)}")

        summary = state.get("analytical_insight_summary")
        if summary:
            st.info(summary)

    st.divider()
    st.markdown("**Agent E — skenario optimasi**")

    if simulation is None:
        st.info("Butuh output Agent D terlebih dahulu.")
        return

    rl_scenarios_json = st.text_area(
        "Keluaran policy RL (rl_scenarios)",
        value=st.session_state.get("rl_scenarios") or "",
        height=200,
        key="rl_scenarios_input",
        placeholder='[{"scenario_id": "scenario_01", "constraints": {...}, "metrics": {...}}]',
    )

    if rl_scenarios_json and st.button("Jalankan optimization_scenario_agent"):
        try:
            rl_scenarios = json.loads(rl_scenarios_json)

        except json.JSONDecodeError as error:
            st.error(f"rl_scenarios bukan JSON valid: {error}")
            return

        payload = {
            "assets": twin.get("assets"),
            "process_stages": twin.get("process_stages"),
            "job_descriptions": read_jobs(twin),
            "workers": workers.get("workers"),
            "factory_flow_rightnow": floor.get("factory_flow_rightnow"),
            "llm_compatibility_and_evaluations": floor.get("llm_compatibility_and_evaluations"),
            "live_simulation_state": simulation.get("live_simulation_state"),
            "rl_scenarios": rl_scenarios,
        }

        with st.spinner("Menyusun narasi skenario..."):
            try:
                result = run_structured_agent(
                    stage="optimal_state",
                    role=AgentRole.OPTIMIZATION_SCENARIO,
                    payload=json.dumps(payload, ensure_ascii=False),
                )
                st.session_state["optimal_state"] = result

            except Exception as error:
                st.error(f"Agent gagal: {type(error).__name__}: {error}")

    optimal = st.session_state["optimal_state"]

    if optimal is not None:
        render_json_result("optimal_state", "Skenario optimasi", optimal)
        st.write(f"Skenario direkomendasikan: {optimal.get('recommended_scenario_id', '-')}")


def tab_reinforcement_learning():
    st.subheader("Tahap 7 — Optimasi Reinforcement Learning")

    required = {
        "Struktur pabrik (Agent A)": st.session_state["factory_structure"],
        "Profil pekerja (Agent B)": st.session_state["worker_profile"],
        "Kondisi lantai (Agent C)": st.session_state["floor_state"],
        "State simulasi (Agent D)": st.session_state["simulation_state"],
    }

    missing = [label for label, value in required.items() if value is None]

    if missing:
        st.info("Selesaikan tahap berikut terlebih dahulu: " + ", ".join(missing))
        return

    if st.session_state["compatibility_matrix"] is None:
        st.warning(
            "Matriks kompatibilitas belum dibangun. Pasangan pekerja x stasiun yang belum "
            "dievaluasi akan diisi heuristik, sehingga rekomendasi kurang tajam."
        )

    if st.button("Bangun snapshot lingkungan RL"):
        try:
            st.session_state["env_snapshot"] = build_snapshot_from_session()

        except FloorStateAlignmentError as error:
            st.session_state["env_snapshot"] = None
            st.error(str(error))
            st.info(
                "Periksa tab 2 (stage_id pada process_stages) dan tab 6 (current_stage_id "
                "pada factory_flow_rightnow). Keduanya harus memakai id yang sama."
            )

        except Exception as error:
            st.session_state["env_snapshot"] = None
            st.error(f"Snapshot gagal dibangun: {type(error).__name__}: {error}")

    snapshot = st.session_state["env_snapshot"]

    if snapshot is None:
        st.info("Bangun snapshot terlebih dahulu sebelum melatih atau menjalankan kebijakan.")
        return

    report = st.session_state.get("floor_alignment_report")

    if report:
        render_alignment_report(report)

    render_snapshot_summary(snapshot)

    st.divider()
    scenario_id = st.selectbox(
        "Skenario batasan",
        list(SCENARIO_LIBRARY.keys()),
        format_func=lambda key: f"{key} — {SCENARIO_TITLES[key]}",
    )
    scenario = SCENARIO_LIBRARY[scenario_id]
    st.caption(
        f"Rekrut: {scenario.hiring_allowed} | Otomasi: {scenario.automation_allowed} | "
        f"Mutasi: {scenario.mutation_allowed} | Capex: Rp{scenario.capex_budget:,.0f}"
    )

    mode = st.radio(
        "Sumber kebijakan",
        options=["Latih kebijakan baru", "Muat policy tersimpan", "Baseline heuristik tanpa RL"],
        horizontal=True,
    )

    if mode == "Latih kebijakan baru":
        columns = st.columns(4)
        timesteps = columns[0].select_slider(
            "Total timesteps",
            options=[25_000, 50_000, 100_000, 200_000, 500_000],
            value=100_000,
        )
        n_envs = columns[1].slider("Environment paralel", 1, 8, 4)
        seed = columns[2].number_input("Seed", min_value=0, value=42, step=1)
        learning_rate = columns[3].select_slider(
            "Learning rate", options=[1e-4, 3e-4, 1e-3], value=3e-4
        )

        if st.button("Latih MaskablePPO", type="primary"):
            config = TrainingConfig(
                total_timesteps=int(timesteps),
                n_envs=int(n_envs),
                learning_rate=float(learning_rate),
                seed=int(seed),
                output_dir=RL_OUTPUT_DIR,
            )

            set_random_seed(config.seed)
            target = config.output_dir / scenario_id
            target.mkdir(parents=True, exist_ok=True)

            progress_bar = st.progress(0.0)
            status_slot = st.empty()

            try:
                train_env = build_training_env(snapshot, scenario, config)
                model = build_model(train_env, config)

                started = time.perf_counter()
                model.learn(
                    total_timesteps=config.total_timesteps,
                    callback=StreamlitProgressCallback(
                        config.total_timesteps, progress_bar, status_slot
                    ),
                )
                elapsed = time.perf_counter() - started

                model.save(str(target / "policy"))
                train_env.save(str(target / "vecnormalize.pkl"))
                train_env.close()

            except Exception as error:
                st.error(f"Pelatihan gagal: {type(error).__name__}: {error}")
                return

            st.session_state["rl_policy"] = model
            st.session_state["rl_policy_scenario"] = scenario_id
            st.session_state["timings"]["rl_training"] = elapsed

            progress_bar.progress(1.0)
            st.success(
                f"Pelatihan selesai dalam {elapsed:.1f} detik. "
                f"Tersimpan di {target / 'policy.zip'}"
            )

    elif mode == "Muat policy tersimpan":
        uploaded = st.file_uploader("Berkas policy (.zip)", type=["zip"], key="rl_policy_upload")

        if uploaded is not None and st.button("Muat policy"):
            RL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            path = RL_OUTPUT_DIR / uploaded.name

            with open(path, "wb") as handle:
                handle.write(uploaded.getbuffer())

            try:
                st.session_state["rl_policy"] = MaskablePPO.load(str(path))
                st.session_state["rl_policy_scenario"] = scenario_id
                st.success(f"Policy dimuat dari {path.name}.")

            except Exception as error:
                st.error(f"Policy gagal dimuat: {type(error).__name__}: {error}")

    else:
        st.info(
            "Mode ini menjalankan penjadwal greedy pada environment dan reward yang sama, "
            "tanpa pelatihan. Berguna sebagai pembanding dasar kebijakan RL."
        )

    st.divider()
    st.markdown("**Jalankan optimasi**")

    use_heuristic = mode == "Baseline heuristik tanpa RL"
    policy = st.session_state["rl_policy"]

    if not use_heuristic and policy is None:
        st.info("Latih atau muat kebijakan terlebih dahulu.")
        return

    sweep = st.checkbox("Sapu semua preset bobot dan ambil frontier Pareto", value=False)

    if sweep:
        labels = list(WEIGHT_PRESETS.keys())
        vectors = [np.array(values, dtype=np.float32) for values in WEIGHT_PRESETS.values()]
    else:
        labels = ["Kustom"]
        vectors = [render_weight_controls().objective_vector()]

    if st.button("Hasilkan rl_scenarios"):
        candidates = []

        with st.spinner("Menjalankan simulasi shift..."):
            started = time.perf_counter()

            try:
                for label, vector in zip(labels, vectors):
                    weights = RewardWeights.from_vector(vector)

                    if use_heuristic:
                        info = heuristic_rollout(snapshot, scenario, weights)
                    else:
                        info = rollout(policy, snapshot, scenario, weights, seed=42)

                    payload = build_scenario_payload(
                        snapshot, scenario_id, scenario, weights, info
                    )
                    payload["preset_label"] = label
                    payload["policy_source"] = "heuristic" if use_heuristic else "maskable_ppo"
                    candidates.append(attach_deltas(payload))

            except Exception as error:
                st.error(f"Rollout gagal: {type(error).__name__}: {error}")
                return

            st.session_state["timings"]["rl_rollout"] = time.perf_counter() - started

        if sweep and len(candidates) > 1:
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
            keep = pareto_front(objectives, np.array([True, False, False, False]))
            candidates = [candidates[int(index)] for index in keep]

        for position, item in enumerate(candidates):
            item["scenario_id"] = f"{scenario_id}_{position + 1:02d}" if len(candidates) > 1 else scenario_id

        st.session_state["rl_candidates"] = candidates
        st.session_state["rl_scenarios"] = json.dumps(candidates, indent=2, ensure_ascii=False)

    candidates = st.session_state["rl_candidates"]

    if not candidates:
        return

    st.divider()

    if len(candidates) > 1:
        st.markdown("**Frontier Pareto**")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "scenario_id": item["scenario_id"],
                        "preset": item.get("preset_label"),
                        "throughput": item["metrics"]["throughput_per_hour"]["after"],
                        "error_pct": item["metrics"]["human_error_rate_pct"]["after"],
                        "biaya_per_item": item["metrics"]["cost_per_item_rp"]["after"],
                        "fatigue_maks": item["metrics"]["max_fatigue"]["after"],
                        "bottleneck": item["metrics"]["bottleneck_count"]["after"],
                        "capex": item["constraints"]["capex_used_rp"],
                    }
                    for item in candidates
                ]
            ),
            use_container_width=True,
        )

        chosen = st.selectbox(
            "Tampilkan detail",
            range(len(candidates)),
            format_func=lambda index: candidates[index]["scenario_id"],
        )
        render_scenario_detail(candidates[chosen])
    else:
        render_scenario_detail(candidates[0])

    st.divider()
    st.caption(
        "Blok di bawah adalah rl_scenarios yang menjadi input Agent E pada tab Pipeline lanjutan."
    )
    st.json(candidates, expanded=False)
    st.download_button(
        label="Unduh rl_scenarios (.json)",
        data=st.session_state["rl_scenarios"],
        file_name="rl_scenarios.json",
        mime="application/json",
        key="download_rl_scenarios",
    )


def tab_chatbot():
    st.subheader("Tahap 8 — Uji chatbot digital twin")

    twin = st.session_state["factory_structure"]
    workers = st.session_state["worker_profile"]
    floor = st.session_state["floor_state"]
    simulation = st.session_state["simulation_state"]
    optimal = st.session_state["optimal_state"]

    readiness = [
        ("Struktur pabrik (Agent A)", twin is not None),
        ("Profil pekerja (Agent B)", workers is not None),
        ("Kondisi lantai (Agent C)", floor is not None),
        ("State simulasi (Agent D)", simulation is not None),
        ("Skenario optimasi (Agent E)", optimal is not None),
    ]

    columns = st.columns(len(readiness))
    for column, (label, ready) in zip(columns, readiness):
        column.metric(label, "siap" if ready else "belum")

    missing = [label for label, ready in readiness if not ready]

    if missing:
        st.warning(
            "Rute yang membutuhkan data berikut akan ditolak: "
            + ", ".join(missing)
            + ". Rute general tetap bisa diuji."
        )

    with st.expander("Tempel optimal_state secara manual"):
        pasted = st.text_area("optimal_state JSON", height=160, key="optimal_state_paste")

        if pasted and st.button("Pakai optimal_state ini"):
            try:
                st.session_state["optimal_state"] = json.loads(pasted)
                st.rerun()

            except json.JSONDecodeError as error:
                st.error(f"JSON tidak valid: {error}")

    if st.session_state["chat_summary"]:
        with st.expander("Ringkasan percakapan berjalan"):
            st.info(st.session_state["chat_summary"])

    for message in st.session_state["chat_messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            if message.get("route"):
                st.caption(f"Rute: {CHAT_ROUTE_LABELS.get(message['route'], message['route'])}")

    with st.form("chat_form", clear_on_submit=True):
        question = st.text_area("Pertanyaan manajer", height=90)
        submitted = st.form_submit_button("Kirim")

    if submitted and question.strip():
        with st.spinner("Merutekan dan menjawab..."):
            try:
                trace = run_chat_turn(
                    question.strip(), twin, workers, floor, simulation, optimal
                )

            except Exception as error:
                st.error(f"Chatbot gagal: {type(error).__name__}: {error}")
                return

        st.session_state["chat_messages"].append(
            {"role": "user", "content": question.strip()}
        )
        st.session_state["chat_messages"].append(
            {"role": "assistant", "content": trace["jawaban"], "route": trace["route"]}
        )
        st.session_state["chat_traces"].append(trace)

        if not trace["terblokir"]:
            try:
                compact_chat_history()

            except Exception as error:
                st.warning(f"Peringkasan riwayat gagal: {error}")

        st.rerun()

    traces = st.session_state["chat_traces"]

    if traces:
        st.divider()
        st.markdown("**Jejak eksekusi**")

        trace_rows = []
        for index, trace in enumerate(traces, start=1):
            trace_rows.append(
                {
                    "giliran": index,
                    "route": trace.get("route"),
                    "terblokir": trace.get("terblokir"),
                    "token_konteks": trace.get("konteks_token_estimasi"),
                    "rewrite_detik": trace.get("rewrite_detik"),
                    "route_detik": trace.get("route_detik"),
                    "jawab_detik": trace.get("jawab_detik"),
                }
            )

        st.dataframe(pd.DataFrame(trace_rows), use_container_width=True)

        selected = st.selectbox(
            "Lihat detail giliran",
            options=list(range(len(traces))),
            format_func=lambda index: f"Giliran {index + 1} — {traces[index].get('route')}",
        )
        st.json(traces[selected], expanded=False)

    if st.button("Reset percakapan"):
        st.session_state["chat_messages"] = []
        st.session_state["chat_summary"] = None
        st.session_state["chat_traces"] = []
        st.rerun()


def tab_metrics():
    st.subheader("Ringkasan eksekusi")

    timings = st.session_state["timings"]
    usages = st.session_state["usages"]

    if not timings:
        st.info("Belum ada agent yang dijalankan.")
        return

    rows = []
    for stage, elapsed in timings.items():
        usage = usages.get(stage, {})
        rows.append(
            {
                "tahap": stage,
                "durasi_detik": round(elapsed, 2),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            }
        )

    frame = pd.DataFrame(rows)
    st.dataframe(frame, use_container_width=True)

    total_time = sum(timings.values())
    st.metric("Total waktu pipeline", f"{total_time:.1f} detik")


def main():
    st.set_page_config(page_title="Digital Twin Pipeline Playground", layout="wide")
    init_session_state()

    st.title("Digital Twin Pipeline Playground")
    st.caption("Uji ekstraksi pabrik, ekstraksi CV pekerja, matriks kompatibilitas, dan pipeline simulasi.")

    render_sidebar()

    tabs = st.tabs(
        [
            "1. Ekstraksi pabrik",
            "2. Struktur pabrik",
            "3. Kelengkapan",
            "4. Pekerja (CV)",
            "5. Kompatibilitas",
            "6. Pipeline lanjutan",
            "7. Optimasi RL",
            "8. Chatbot",
            "9. Metrik",
        ]
    )

    with tabs[0]:
        tab_extraction()

    with tabs[1]:
        tab_structure()

    with tabs[2]:
        tab_completeness()

    with tabs[3]:
        tab_worker_extraction()

    with tabs[4]:
        tab_compatibility()

    with tabs[5]:
        tab_downstream()

    with tabs[6]:
        tab_reinforcement_learning()

    with tabs[7]:
        tab_chatbot()

    with tabs[8]:
        tab_metrics()


if __name__ == "__main__":
    main()