import json
import sys
import time
from pathlib import Path

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # PABRIKERS_COMPFEST/
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
    build_agent_input,
    extract_document,
)
from backend.app.services.check_factory_completeness import (
    GapSeverity,
    check_factory_completeness,
)


UPLOAD_DIR = Path("/tmp/pabrikers_playground")
STAGE_KEYS = [
    "extracted_document",
    "agent_input",
    "factory_structure",
    "completeness_report",
    "clarification_text",
    "worker_profile",
    "floor_state",
    "simulation_state",
]


def init_session_state():
    for key in STAGE_KEYS:
        if key not in st.session_state:
            st.session_state[key] = None

    if "timings" not in st.session_state:
        st.session_state["timings"] = {}

    if "usages" not in st.session_state:
        st.session_state["usages"] = {}


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


def tab_extraction():
    st.subheader("Tahap 1 — Ekstraksi dokumen")

    mode = st.radio(
        "Sumber input",
        options=["Unggah file", "Tempel teks manual"],
        horizontal=True,
        key="extraction_mode",
    )

    if mode == "Unggah file":
        uploaded = st.file_uploader(
            "Dokumen pabrik",
            type=["pdf", "docx", "md", "markdown", "txt"],
        )

        if uploaded is not None and st.button("Ekstrak dokumen"):
            saved_path = persist_upload(uploaded)

            try:
                document = extract_document(saved_path)

            except UnsupportedDocumentError as error:
                st.error(str(error))
                return

            except Exception as error:
                st.error(f"Ekstraksi gagal: {error}")
                return

            st.session_state["extracted_document"] = document
            st.session_state["agent_input"] = build_agent_input(document)

    else:
        pasted = st.text_area(
            "Tempel dokumen dalam format tetap",
            height=320,
            placeholder="Nama pabrik: ...\nJenis proses: ...\nDeskripsi pabrik: ...\nJumlah pekerja: ...",
        )

        if pasted and st.button("Gunakan teks ini"):
            st.session_state["extracted_document"] = None
            st.session_state["agent_input"] = pasted

    document = st.session_state["extracted_document"]

    if document is not None:
        st.divider()
        st.markdown("**Field teks terbaca**")

        field_rows = []
        for key, value in document.text_fields.items():
            field_rows.append({"field": key, "nilai": value})

        if field_rows:
            st.dataframe(pd.DataFrame(field_rows), use_container_width=True)
        else:
            st.warning("Tidak ada field teks yang terbaca dari dokumen.")

        missing = document.missing_text_fields()
        if missing:
            st.warning(f"Field yang belum terbaca: {', '.join(missing)}")

        st.markdown(f"**Tabel terdeteksi: {len(document.tables)}**")

        if len(document.tables) < 3:
            st.warning(
                "Format baku mengharapkan tiga tabel. "
                "Hasil Agent A kemungkinan tidak lengkap."
            )

        for table in document.tables:
            with st.expander(f"Tabel {table.index} — {len(table.rows)} baris"):
                st.dataframe(
                    pd.DataFrame(table.rows, columns=table.headers),
                    use_container_width=True,
                )

        with st.expander("Teks mentah hasil ekstraksi"):
            st.text(document.raw_text)

    if st.session_state["agent_input"]:
        st.divider()
        st.markdown("**Payload yang akan dikirim ke Agent A**")
        edited = st.text_area(
            "Bisa disunting sebelum dikirim",
            value=st.session_state["agent_input"],
            height=280,
            key="agent_input_editor",
        )
        st.session_state["agent_input"] = edited


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
    columns = st.columns(4)
    columns[0].metric("Tahapan", len(info.get("workflow_sequence", [])))
    columns[1].metric("Aset", len(twin.get("assets", [])))
    columns[2].metric("Job desk", len(twin.get("job_descriptions", [])))
    columns[3].metric("Jenis proses", info.get("process_type", "-"))

    asset_rows = []
    for asset in twin.get("assets", []):
        asset_rows.append(
            {
                "asset_id": asset.get("asset_id"),
                "nama": asset.get("asset_name"),
                "tahapan": asset.get("workflow_step"),
                "otomatis": asset.get("is_automated"),
                "unit": asset.get("units_available"),
                "kapasitas": asset.get("base_throughput_capacity"),
                "strain": asset.get("environmental_factors", {}).get("physical_strain_index"),
            }
        )

    if asset_rows:
        st.markdown("**Ringkasan aset**")
        st.dataframe(pd.DataFrame(asset_rows), use_container_width=True)

    job_rows = []
    for job in twin.get("job_descriptions", []):
        demands = job.get("demands", {})
        job_rows.append(
            {
                "job_id": job.get("job_id"),
                "judul": job.get("job_title"),
                "tahapan": job.get("workflow_step"),
                "aset": job.get("assigned_asset_id"),
                "pekerja": ", ".join(job.get("assigned_worker_names", [])),
                "fokus": demands.get("required_cognitive_focus"),
                "severity": demands.get("error_severity"),
            }
        )

    if job_rows:
        st.markdown("**Ringkasan job desk**")
        st.dataframe(pd.DataFrame(job_rows), use_container_width=True)


def tab_completeness():
    st.subheader("Tahap 3 — Pemeriksaan kelengkapan")

    twin = st.session_state["factory_structure"]

    manual_json = st.text_area(
        "Atau tempel JSON digital twin langsung untuk diuji",
        height=180,
        key="manual_twin_json",
    )

    if manual_json and st.button("Periksa JSON tempelan"):
        try:
            twin = json.loads(manual_json)
            st.session_state["factory_structure"] = twin

        except json.JSONDecodeError as error:
            st.error(f"JSON tidak valid: {error}")
            return

    if twin is None:
        st.info("Belum ada struktur pabrik untuk diperiksa.")
        return

    report = check_factory_completeness(twin)
    st.session_state["completeness_report"] = report

    columns = st.columns(3)
    columns[0].metric("Status", "Lengkap" if report.is_complete else "Belum lengkap")
    columns[1].metric("Blocking", report.blocking_count)
    columns[2].metric("Warning", report.warning_count)

    if report.gaps:
        gap_rows = []
        for gap in report.gaps:
            gap_rows.append(
                {
                    "severity": str(gap.severity),
                    "path": gap.path,
                    "masalah": gap.message,
                    "pertanyaan": gap.question,
                }
            )

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

    else:
        st.success("Tidak ada field yang kurang.")

    if st.session_state["clarification_text"]:
        st.markdown("**Pertanyaan untuk user**")
        st.info(st.session_state["clarification_text"])


def tab_downstream():
    st.subheader("Tahap 4 — Pipeline lanjutan")

    twin = st.session_state["factory_structure"]

    if twin is None:
        st.info("Selesaikan Agent A terlebih dahulu.")
        return

    st.markdown("**Agent B — profil pekerja**")
    worker_input = st.text_area(
        "Data pekerja (CV, daftar HR, atau log shift)",
        height=200,
        key="worker_input",
    )

    if worker_input and st.button("Jalankan worker_profile_agent"):
        with st.spinner("Memproses profil pekerja..."):
            try:
                result = run_structured_agent(
                    stage="worker_profile",
                    role=AgentRole.WORKER_PROFILE,
                    payload=worker_input,
                )
                st.session_state["worker_profile"] = result

            except Exception as error:
                st.error(f"Agent gagal: {error}")

    workers = st.session_state["worker_profile"]

    if workers is not None:
        render_json_result("worker_profile", "Profil pekerja", workers)

    st.divider()
    st.markdown("**Agent C — kondisi lantai produksi**")

    if workers is None:
        st.info("Butuh output Agent B terlebih dahulu.")
        return

    if st.button("Jalankan floor_state_agent"):
        payload = {
            "factory_info": twin.get("factory_info"),
            "assets": twin.get("assets"),
            "job_descriptions": twin.get("job_descriptions"),
            "workers": workers.get("workers"),
        }

        with st.spinner("Menempatkan pekerja..."):
            try:
                result = run_structured_agent(
                    stage="floor_state",
                    role=AgentRole.FLOOR_STATE,
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
            "job_descriptions": twin.get("job_descriptions"),
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

        if metric_rows:
            st.dataframe(pd.DataFrame(metric_rows), use_container_width=True)

        bottlenecks = state.get("system_bottlenecks", [])
        if bottlenecks:
            st.warning(f"Bottleneck: {', '.join(bottlenecks)}")

        summary = state.get("analytical_insight_summary")
        if summary:
            st.info(summary)


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
    st.caption("Uji ekstraksi dokumen, Agent A, pemeriksaan kelengkapan, dan pipeline lanjutan.")

    render_sidebar()

    tabs = st.tabs(
        [
            "1. Ekstraksi",
            "2. Struktur pabrik",
            "3. Kelengkapan",
            "4. Pipeline lanjutan",
            "5. Metrik",
        ]
    )

    with tabs[0]:
        tab_extraction()

    with tabs[1]:
        tab_structure()

    with tabs[2]:
        tab_completeness()

    with tabs[3]:
        tab_downstream()

    with tabs[4]:
        tab_metrics()


if __name__ == "__main__":
    main()