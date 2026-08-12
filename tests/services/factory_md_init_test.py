import json
import sys
import time
from pathlib import Path
import copy
import re

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
from backend.app.services.extract_xlsx_input_service import (
    apply_repairs,
    build_workbook
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
)

from backend.app.services.generate_worker_profiles_service import (
    WorkerProfileGenerationError,
    generate_worker_profiles
)

from backend.app.services.cv_pdf_parser_service import candidate_payload


UPLOAD_DIR = Path("/tmp/pabrikers_playground")
STAGE_KEYS = [
    "extracted_document",
    "agent_input",
    "factory_structure",
    "completeness_report",
    "clarification_text",
    "worker_document",
    "worker_archive_reports",
    "worker_agent_input",
    "worker_profile",
    "compatibility_matrix",
    "floor_state",
    "simulation_state",
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

    if st.button("Jalankan factory_structure_agent"):
        with st.spinner("Menghubungi vLLM..."):
            try:
                result = run_structured_agent(
                    stage="factory_structure",
                    role=AgentRole.FACTORY_STRUCTURE,
                    payload=payload,
                )
                st.session_state["factory_structure"] = result

            except Exception as error:
                st.error(f"Agent gagal: {type(error).__name__}: {error}")
                return

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

            st.session_state["timings"]["worker_profile"] = elapsed
            st.session_state["worker_profile"] = result
            st.success(
                f"{result['meta']['processed_count']}/{result['meta']['candidate_count']} "
                f"kandidat selesai dalam {elapsed:.2f} detik "
                f"({result['meta']['retries']} percobaan ulang)."
            )

            if result["meta"]["failures"]:
                st.warning("Sebagian kandidat gagal dan dikeluarkan dari hasil.")
                st.dataframe(pd.DataFrame(result["meta"]["failures"]), use_container_width=True)

    if st.session_state["worker_agent_input"]:
        st.divider()
        st.markdown("**Payload yang akan dikirim ke Agent B**")
        edited = st.text_area(
            "Bisa disunting sebelum dikirim",
            value=st.session_state["worker_agent_input"],
            height=280,
            key="worker_agent_input_editor",
        )
        st.session_state["worker_agent_input"] = edited

        if st.button("Jalankan cv_to_worker_profile_creator"):
            with st.spinner("Memproses profil pekerja..."):
                try:
                    result = run_structured_agent(
                        stage="worker_profile",
                        role=AgentRole.WORKER_PROFILE,
                        payload=st.session_state["worker_agent_input"],
                    )
                    st.session_state["worker_profile"] = result

                except Exception as error:
                    st.error(f"Agent gagal: {type(error).__name__}: {error}")

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

    max_workers = st.slider("Panggilan paralel", min_value=1, max_value=12, value=4)
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

    if st.button("Jalankan floor_state_agent"):
        payload = {
            "factory_info": twin.get("factory_info"),
            "shifts": twin.get("shifts"),
            "assets": twin.get("assets"),
            "process_stages": twin.get("process_stages"),
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
                st.session_state["floor_state"] = result

            except Exception as error:
                st.error(f"Agent gagal: {error}")

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
            "7. Chatbot",
            "8. Metrik"
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
        tab_chatbot()

    with tabs[7]:
        tab_metrics()


if __name__ == "__main__":
    main()