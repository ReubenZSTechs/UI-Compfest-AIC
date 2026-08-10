import json
import sys
import time
from pathlib import Path

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
    is_workbook,
    validate_workbook,
    apply_repairs,
    build_workbook,
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
    st.subheader("Tahap 1 — Ekstraksi workbook")

    uploaded = st.file_uploader("Workbook pabrik", type=["xlsx", "xlsm", "pdf", "docx", "md"])

    if uploaded is not None and st.button("Ekstrak"):
        saved_path = persist_upload(uploaded)

        try:
            source = extract_any(saved_path)

        except (UnsupportedDocumentError, UnsupportedWorkbookError) as error:
            st.error(str(error))
            return

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
    columns = st.columns(4)
    columns[0].metric("Tahapan", len(info.get("workflow_sequence", [])))
    columns[1].metric("Aset", len(twin.get("assets", [])))
    columns[2].metric("Job desk", len(read_jobs(twin)))
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
    for job in read_jobs(twin):
        demands = job.get("demands", {})
        job_rows.append(
            {
                "job_id": job.get("job_id"),
                "judul": job.get("job_title"),
                "tahapan": job.get("workflow_step"),
                "aset": job.get("assigned_asset_id"),
                "fokus": demands.get("required_cognitive_focus"),
                "fisik": demands.get("physical_demand_level"),
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

    if document is not None:
        st.divider()

        columns = st.columns(3)
        columns[0].metric("Kandidat terbaca", len(document.candidates))
        columns[1].metric("Berkas sumber", len(set(document.source_names)))
        columns[2].metric("Blok ditolak", len(document.rejected_blocks))

        candidate_rows = []
        for candidate in document.candidates:
            derived = candidate.derived
            candidate_rows.append(
                {
                    "worker_id": candidate.worker_id,
                    "nama": derived.get("name"),
                    "usia": derived.get("age"),
                    "gender": derived.get("gender"),
                    "pengalaman": derived.get("years_of_experience"),
                    "jam_hari_ini": derived.get("hours_worked_today"),
                    "shift_beruntun": derived.get("consecutive_shifts"),
                    "sumber": candidate.source_name,
                    "field_kosong": ", ".join(candidate.missing_fields()),
                }
            )

        if candidate_rows:
            st.dataframe(pd.DataFrame(candidate_rows), use_container_width=True)

        if document.rejected_blocks:
            st.warning("Sebagian berkas tidak dianggap CV dan dikeluarkan dari daftar pekerja.")
            st.dataframe(pd.DataFrame(document.rejected_blocks), use_container_width=True)

        missing = document.missing_fields()
        if missing:
            st.warning(
                "Field belum terbaca: "
                + "; ".join(f"{key} ({', '.join(values)})" for key, values in missing.items())
            )

            if st.button("Susun pertanyaan klarifikasi pekerja"):
                payload = "\n".join(
                    f"{candidate.worker_id} — {candidate.derived.get('name') or 'nama tidak terbaca'} "
                    f"(berkas {candidate.source_name}): {', '.join(candidate.missing_fields())}"
                    for candidate in document.candidates
                    if candidate.missing_fields()
                )

                with st.spinner("Menyusun pertanyaan..."):
                    try:
                        text = run_text_agent(
                            stage="cv_clarification",
                            role=AgentRole.CV_CLARIFICATION,
                            payload=payload,
                        )
                        st.info(text)

                    except Exception as error:
                        st.error(f"Agent klarifikasi gagal: {error}")

        for candidate in document.candidates:
            with st.expander(f"{candidate.worker_id} — {candidate.source_name}"):
                for key, value in candidate.sections.items():
                    st.markdown(f"**{key}**")
                    st.text(value)

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

    worker_list = workers.get("workers", [])
    job_list = read_jobs(twin)

    columns = st.columns(3)
    columns[0].metric("Pekerja", len(worker_list))
    columns[1].metric("Job desk", len(job_list))
    columns[2].metric("Pasangan", len(worker_list) * len(job_list))

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
            "7. Metrik",
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
        tab_metrics()


if __name__ == "__main__":
    main()