from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Factory(Base):
    """
    Root entity: satu pabrik/factory sebagai parent dari seluruh data digital twin.

    Sumber data (constants.py -> factory_info):
        factory_id   : "fac-xyz-ygy-01"
        factory_name : "Sweet Bread, PT XYZ Yogyakarta"
        workflow_sequence (JSONB, list[str], 10 items) :
            [
                "step_01_weighing", "step_02_mixing", "step_03_dough_dividing",
                "step_04_dough_shaping", "step_05_filling_panning", "step_06_proofing",
                "step_07_baking", "step_08_cooling", "step_09_sorting", "step_10_packaging",
            ]

    Cardinality: 1 row per factory. Saat ini hanya 1 factory (fac-xyz-ygy-01).

    Cascade: menghapus Factory akan menghapus SEMUA child-nya (assets, job_desks,
    workers, flow_snapshots, evaluations) via cascade="all, delete-orphan".
    """
    __tablename__ = "factories"

    factory_id: Mapped[str] = mapped_column(String, primary_key=True)
    factory_name: Mapped[str] = mapped_column(String, nullable=False)
    workflow_sequence: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    assets: Mapped[list["Asset"]] = relationship(back_populates="factory", cascade="all, delete-orphan")
    job_desks: Mapped[list["JobDesk"]] = relationship(back_populates="factory", cascade="all, delete-orphan")
    workers: Mapped[list["Worker"]] = relationship(back_populates="factory", cascade="all, delete-orphan")
    flow_snapshots: Mapped[list["FactoryFlowSnapshot"]] = relationship(back_populates="factory", cascade="all, delete-orphan")
    evaluations: Mapped[list["CompatibilityEvaluation"]] = relationship(back_populates="factory", cascade="all, delete-orphan")


class Asset(Base):
    """
    Mesin/peralatan/stasiun kerja pada tiap tahap workflow produksi.

    Sumber data:
        asset_id     : "ast-07"
        asset_name   : "Deck Oven / Combi Oven"
        category     : "machine" | "measuring_equipment" | "conveyor_automation"
                       | "environmental_chamber" | "manual_station"
        workflow_step: "step_07_baking"  (1:1 dengan salah satu step di workflow_sequence)
        is_automated : True | False
                       -> False untuk ast-08 (Cooling Area) dan ast-09 (Sorting Station),
                          karena sumber tabel asli menandai kolom otomatisasi dengan "—"
        base_throughput_capacity  : 220        (unit/jam, angka estimasi)
        operational_cost_per_hour : 18.0       (angka estimasi)
        environmental_factors (JSONB):
            {
                "noise_level_db": 58,
                "vibration_hazard_level": "low" | "medium",
                "physical_strain_index": 0.55   (0.0 - 1.0)
            }
        metric_derivation_reasoning: teks penjelasan asal-usul angka di atas, mis.
            "Oven menghasilkan panas tinggi (bahaya panas, bukan kebisingan) sehingga
             physical_strain_index dinaikkan. QC kritikal: suhu 170°C selama 8-10 menit..."

    Cardinality: 10 rows, satu asset per workflow_step (relasi 1:1 step<->asset
    pada seed data ini, meskipun skema tidak memaksakan itu).

    FK: job_desks.assigned_asset_id -> assets.asset_id (ondelete="RESTRICT",
    asset tidak bisa dihapus selama masih dipakai job desk).
    """
    __tablename__ = "assets"

    asset_id: Mapped[str] = mapped_column(String, primary_key=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), nullable=False, index=True)
    asset_name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    workflow_step: Mapped[str] = mapped_column(String, nullable=False, index=True)
    is_automated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    base_throughput_capacity: Mapped[float] = mapped_column(Float, nullable=False)
    operational_cost_per_hour: Mapped[float] = mapped_column(Float, nullable=False)
    # { noise_level_db, vibration_hazard_level, physical_strain_index }
    environmental_factors: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metric_derivation_reasoning: Mapped[str] = mapped_column(Text, nullable=False)

    factory: Mapped["Factory"] = relationship(back_populates="assets")
    job_desks: Mapped[list["JobDesk"]] = relationship(back_populates="assigned_asset")


class JobDesk(Base):
    """
    Posisi/peran kerja spesifik pada tiap tahap workflow, terikat ke satu Asset.

    Sumber data:
        job_id            : "job-09"
        job_title         : "Inspektur Sortir"
        workflow_step     : "step_09_sorting"
        assigned_asset_id : "ast-09"   (FK -> assets.asset_id, relasi 1:1 per job)
        demands (JSONB):
            {
                "required_cognitive_focus": 0.9,      (0.0 - 1.0)
                "physical_demand_level": "low" | "medium" | "high",
                "task_complexity": 0.5,               (0.0 - 1.0)
                "error_severity": "low" | "moderate" | "high" | "critical"
            }
        qc_requirement: teks kriteria QC, mis.
            "Memeriksa produk cacat: gosong, filling bocor, lengket, hancur,
             kurang matang, tidak mengembang, tanpa topping, ukuran tidak sesuai..."
            -> boleh string kosong/"Tidak ada QC eksplisit..." jika sumber asli
               tidak mencantumkan syarat QC untuk step tsb.
        metric_derivation_reasoning: penjelasan asal-usul nilai demands di atas.

    Cardinality: 10 rows, satu job desk per workflow_step.

    Rentang demands di seluruh dataset:
        required_cognitive_focus : 0.3 (step_08_cooling) - 0.9 (step_09_sorting)
        error_severity            : "low" (job-08, job-10) - "critical" (job-07 baking)
    """
    __tablename__ = "job_desks"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), nullable=False, index=True)
    job_title: Mapped[str] = mapped_column(String, nullable=False)
    workflow_step: Mapped[str] = mapped_column(String, nullable=False, index=True)
    assigned_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id", ondelete="RESTRICT"), nullable=False)
    # { required_cognitive_focus, physical_demand_level, task_complexity, error_severity }
    demands: Mapped[dict] = mapped_column(JSONB, nullable=False)
    qc_requirement: Mapped[str] = mapped_column(Text, nullable=False)
    metric_derivation_reasoning: Mapped[str] = mapped_column(Text, nullable=False)

    factory: Mapped["Factory"] = relationship(back_populates="job_desks")
    assigned_asset: Mapped["Asset"] = relationship(back_populates="job_desks")


class Worker(Base):
    """
    Data pekerja/staf pabrik, terpisah atribut statis (demographics) dan
    atribut dinamis harian (shift_context).

    Sumber data (constants.py -> workers[], 10 rows: wrk-01 s/d wrk-10):
        worker_id : "wrk-07"
        name      : "Bambang Setiawan"
        demographics (JSONB, relatif statis):
            {
                "age": 45,
                "gender": "male" | "female",
                "years_of_experience": 18,
                "baseline_physical_stamina": 0.65,   (0.0 - 1.0)
                "cognitive_resilience": 0.9           (0.0 - 1.0)
            }
        shift_context (JSONB, berubah per hari/shift):
            {
                "hours_worked_today": 5.0,
                "consecutive_shifts": 5
            }

    Cardinality: 10 rows.

    Catatan variasi data: worker didesain dengan trade-off realistis, mis.
    wrk-07 (senior, exp 18 thn, cognitive_resilience 0.9 tapi stamina rendah 0.65)
    vs wrk-08 (junior, exp 2 thn, stamina tinggi 0.88 tapi cognitive_resilience
    rendah 0.6) -> dipakai untuk menghasilkan skor kompatibilitas yang bervariasi
    pada compatibility_evaluations.
    """
    __tablename__ = "workers"

    worker_id: Mapped[str] = mapped_column(String, primary_key=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # { age, gender, years_of_experience, baseline_physical_stamina, cognitive_resilience }
    demographics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # { hours_worked_today, consecutive_shifts }
    shift_context: Mapped[dict] = mapped_column(JSONB, nullable=False)

    factory: Mapped["Factory"] = relationship(back_populates="workers")


class FactoryFlowSnapshot(Base):
    """
    Satu row = satu snapshot kondisi lantai produksi pada satu titik waktu
    (bisa banyak snapshot seiring waktu -> time-series/replay pattern).

    Sumber data (constants.py -> factory_flow_rightnow, header saja;
    detail per-worker ada di StaffPosition):
        snapshot_timestamp : "2026-07-27T09:30:00+07:00"
        note : "Snapshot kondisi lantai produksi saat ini: posisi tiap staf,
                tahap yang sedang dikerjakan, dan tujuan perpindahan (hand-off)
                ke tahap berikutnya dalam alur linear step_01 -> step_10."

    Cardinality saat ini: 1 snapshot row, dengan 10 StaffPosition anak
    (satu snapshot "healthy state" di mana semua 10 step berjalan simultan).

    Cascade: menghapus snapshot akan menghapus semua staff_positions terkait.
    """
    __tablename__ = "factory_flow_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    factory: Mapped["Factory"] = relationship(back_populates="flow_snapshots")
    staff_positions: Mapped[list["StaffPosition"]] = relationship(back_populates="snapshot", cascade="all, delete-orphan")


class StaffPosition(Base):
    """
    Posisi & aktivitas satu worker pada satu snapshot tertentu (child dari
    FactoryFlowSnapshot).

    Sumber data (constants.py -> factory_flow_rightnow.staff_current_positions[],
    10 rows: wrk-01 s/d wrk-10, satu row per worker per snapshot):
        worker_id           : "wrk-06"
        current_station     : "step_06_proofing"
        current_asset_id    : "ast-06"
        activity_status     : "processing" | "waiting_on_machine"
                               | "idle_waiting_input"
        moving_to_next_step : "step_07_baking"  (atau "finished_goods_storage"
                               untuk worker di step_10_packaging)
        handoff_item        : "loyang proofing #B-236 (25 menit tersisa)"
                               -> teks bebas, kadang menyisipkan info numerik
                                  (mis. sisa waktu) yang TIDAK ter-strukturisasi
                                  sebagai field terpisah; perlu di-parse manual
                                  bila dipakai untuk logic/timer di simulation
                                  engine.

    Cardinality: 10 rows per snapshot (satu per worker aktif), 1:1 dengan
    workers pada snapshot ini.

    Contoh kondisi non-"processing" di seed data:
        wrk-06 (proofing) -> "waiting_on_machine" (masih menunggu proses mesin)
        wrk-08 (cooling)  -> "idle_waiting_input"  (bottleneck dari step baking)
    """
    __tablename__ = "staff_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("factory_flow_snapshots.id", ondelete="CASCADE"), nullable=False, index=True)
    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.worker_id", ondelete="CASCADE"), nullable=False)
    current_station: Mapped[str] = mapped_column(String, nullable=False)
    current_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"), nullable=False)
    activity_status: Mapped[str] = mapped_column(String, nullable=False)
    moving_to_next_step: Mapped[str] = mapped_column(String, nullable=False)
    handoff_item: Mapped[str] = mapped_column(Text, nullable=False)

    snapshot: Mapped["FactoryFlowSnapshot"] = relationship(back_populates="staff_positions")


class CompatibilityEvaluation(Base):
    """
    Hasil evaluasi kompatibilitas worker x job_desk x asset, dipakai oleh
    RL/matching engine.

    Sumber data (constants.py -> generate_full_compatibility_matrix()):
    di-generate saat modul di-import, HASIL CARTESIAN PRODUCT
    10 workers x 10 job_desks = 100 rows. asset_id per row diambil dari
    job["assigned_asset_id"], jadi bukan variabel independen (selalu
    redundan dengan job_desks.assigned_asset_id).

        worker_id : "wrk-07"
        job_id    : "job-07"
        asset_id  : "ast-07"          (ikut assigned_asset_id milik job)
        evaluations (JSONB):
            {
                "overall_compatibility_score": 0.72,   (clamp 0.35 - 0.98)
                "throughput_multiplier": 1.05,          (clamp 0.70 - 1.25)
                "error_multiplier": 0.68,               (clamp 0.35 - 1.50)
                "fatigue_accumulation_rate": 0.95,      (clamp 0.30 - 1.60)
                "stress_sensitivity_factor": 0.55       (clamp 0.40 - 0.95)
            }
        llm_reasoning: string hasil f-string template Python (BUKAN benar-benar
            dihasilkan oleh LLM call), contoh pola:
            "{name} ({exp} thn exp, stamina {stamina}, resiliensi {cog})
             dievaluasi pada {job_title}. Kapasitas kognitif {cog_eval}
             untuk tuntutan tugas ({req_cog}), sedangkan beban fisik
             {phys_eval}. Kondisi shift ({hrs} jam kerja, {shifts} shift
             beruntun) mempengaruhi laju kelelahan ({fatigue_rate}x)."

    Cardinality: 100 rows (10 workers x 10 job_desks) untuk 1 factory.

    Catatan: field llm_reasoning dinamai seolah hasil LLM, padahal saat ini
    masih mock/template deterministik -> perlu ditandai jelas kalau nanti
    diganti generate asli via LLM call, biar tidak tertukar dengan
    metric_derivation_reasoning di Asset/JobDesk yang juga bersifat serupa.
    """
    __tablename__ = "compatibility_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), nullable=False, index=True)
    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.worker_id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("job_desks.job_id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id", ondelete="CASCADE"), nullable=False)
    # { overall_compatibility_score, throughput_multiplier, error_multiplier,
    #   fatigue_accumulation_rate, stress_sensitivity_factor }
    evaluations: Mapped[dict] = mapped_column(JSONB, nullable=False)
    llm_reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    factory: Mapped["Factory"] = relationship(back_populates="evaluations")