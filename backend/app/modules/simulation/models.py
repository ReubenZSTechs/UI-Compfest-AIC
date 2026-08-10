from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SimulationStation(Base):
    """
    Satu row = satu stasiun (ordinal 1..10) untuk satu factory.
    Gabungan dari materials_by_ordinal, step_names, step_cost_base,
    capacity_by_ordinal, batch_in/out_by_ordinal, cycle_ticks_by_ordinal
    -- semua field lama itu sama-sama diindex per ordinal, jadi satu tabel.

    Sumber data (constants.py, semua dict diindex per ordinal 1..10):
        ordinal        : 7
        step_name      : STEP_NAMES[7]        -> "Baking Process"
        material_name  : MATERIAL_BY_ORDINAL[7]["name"]  -> "Loyang Panggang"
        material_unit  : MATERIAL_BY_ORDINAL[7]["unit"]  -> "loyang"
        step_cost_base : STEP_COST_BASE[7]     -> 2_500_000  (Rupiah, termahal
                          di seluruh stasiun -- baking paling capital-intensive)
        capacity       : CAPACITY_BY_ORDINAL[7]-> 28
        batch_in       : BATCH_IN_BY_ORDINAL[7] -> 14
        batch_out      : BATCH_OUT_BY_ORDINAL[7]-> 168  (naik drastis dari
                          batch_in -- satu loyang panggang menghasilkan banyak
                          pcs roti, beda satuan input vs output di step ini)
        cycle_ticks    : CYCLE_TICKS_BY_ORDINAL[7] -> 5  (tick terlama, sesuai
                          durasi baking yang paling lama di antara 10 stasiun)

    Cardinality: 10 rows per factory (ordinal 1-10), unique constraint
    (factory_id, ordinal) mencegah duplikasi stasiun dalam factory yang sama.

    Catatan mass balance (RECIPE TABLE di constants.py adalah single source
    of truth): batch_in/batch_out TIDAK selalu 1:1 -- mis. ordinal 2 (Mixing)
    batch_in=18 tapi batch_out=252 (unit berubah dari kg bahan campur ke
    hasil akhir dalam satuan berbeda), sehingga logic simulation engine harus
    treat tiap ordinal sebagai konversi unit yang independen, bukan sekadar
    pengurangan linear.
    """
    __tablename__ = "simulation_stations"
    __table_args__ = (UniqueConstraint("factory_id", "ordinal", name="uq_simulation_stations_factory_ordinal"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)  # posisi 1..10 dalam workflow

    step_name: Mapped[str] = mapped_column(String, nullable=False)
    material_name: Mapped[str] = mapped_column(String, nullable=False)
    material_unit: Mapped[str] = mapped_column(String, nullable=False)

    step_cost_base: Mapped[int] = mapped_column(Integer, nullable=False)
    capacity: Mapped[float] = mapped_column(Float, nullable=False)
    batch_in: Mapped[float] = mapped_column(Float, nullable=False)
    batch_out: Mapped[float] = mapped_column(Float, nullable=False)
    cycle_ticks: Mapped[int] = mapped_column(Integer, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    factory: Mapped["Factory"] = relationship()  # type: ignore[name-defined]  # noqa: F821


class SimulationSettings(Base):
    """
    Singleton config per factory (threshold, warehouse, jadwal shift).

    Sumber data (constants.py, konstanta top-level, satu nilai berlaku untuk
    seluruh factory -- bukan per-ordinal):
        bottleneck_fill_threshold : BOTTLENECK_FILL_THRESHOLD -> 0.7
                                     (stasiun dianggap bottleneck saat terisi >=70%)
        idle_qty_threshold        : IDLE_QTY_THRESHOLD -> 0.05
                                     (dianggap idle bila qty tersisa <=5%)
        station_1_safety_margin   : STATION_1_SAFETY_MARGIN -> 0.03

        warehouse_capacity : WAREHOUSE_CAPACITY -> 4000
        warehouse_feed_rate: WAREHOUSE_FEED_RATE -> 9
        warehouse_step_id  : WAREHOUSE_STEP_ID -> "warehouse"
                              -> HARUS SAMA PERSIS dengan `WAREHOUSE_STEP_ID` di
                                 frontend `simulation.types.ts`; kalau berubah di
                                 salah satu sisi, sisi lain wajib disesuaikan.

        shift_start_minutes : SHIFT_START_MINUTES -> 480   (08:00, dalam menit)
        break_start_elapsed : BREAK_START_ELAPSED -> 240   (elapsed menit, 12:00)
        break_end_elapsed   : BREAK_END_ELAPSED   -> 300   (elapsed menit, 13:00)
        shift_end_elapsed   : SHIFT_END_ELAPSED   -> 540   (elapsed menit, 17:00)

        analytical_insight_summary : INSIGHT -> teks ringkasan naratif, mis.
            "Simulasi dinamis aktif. Pos dengan multi-worker memiliki kapasitas
             pemrosesan lebih tinggi dan menghabiskan material lebih cepat..."
        target_output_units : TARGET_OUTPUT_UNITS -> 2500.0
        initial_batch_seq   : nilai awal counter batch (mis. penomoran #B-xxx
                               yang dipakai di handoff_item pada module
                               digital_twin_ingestion)

    Cardinality: 1 row per factory (factory_id sekaligus primary key --
    memaksa singleton, tidak mungkin ada 2 baris settings untuk factory yang
    sama).
    """
    __tablename__ = "simulation_settings"

    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), primary_key=True)

    bottleneck_fill_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    idle_qty_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    station_1_safety_margin: Mapped[float] = mapped_column(Float, nullable=False)

    warehouse_capacity: Mapped[float] = mapped_column(Float, nullable=False)
    warehouse_feed_rate: Mapped[float] = mapped_column(Float, nullable=False)
    warehouse_step_id: Mapped[str] = mapped_column(String, nullable=False)

    shift_start_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    break_start_elapsed: Mapped[int] = mapped_column(Integer, nullable=False)
    break_end_elapsed: Mapped[int] = mapped_column(Integer, nullable=False)
    shift_end_elapsed: Mapped[int] = mapped_column(Integer, nullable=False)

    analytical_insight_summary: Mapped[str] = mapped_column(Text, nullable=False)
    target_output_units: Mapped[float] = mapped_column(Float, nullable=False)
    initial_batch_seq: Mapped[int] = mapped_column(Integer, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class WorkerThroughputMultiplier(Base):
    """
    1:1 dengan Worker (module digital_twin_ingestion). Dipisah ke module
    simulation supaya tidak mencampur data 'identitas worker' (HR) dengan
    'parameter tuning simulasi' -- dua concern yang siklus editnya beda.

    Sumber data (constants.py -> WORKER_THROUGHPUT_MULTIPLIER, 11 entries):
        worker_id  : "wrk-07"
        multiplier : 1.15   (tertinggi di seluruh dataset -- worker paling
                     senior/berpengalaman, ditugaskan di tim baking)

    Semua nilai di seed data:
        wrk-01: 1.05, wrk-02: 1.10, wrk-03: 1.00, wrk-04: 1.08, wrk-05: 1.05,
        wrk-06: 1.00, wrk-11: 1.04  (Proofing team, 2 workers),
        wrk-07: 1.15, wrk-12: 1.10 (Baking team, 2 workers),
        wrk-08: 0.95 (terendah), wrk-09: 1.00, wrk-10: 1.02

    Catatan penting: ada wrk-11 dan wrk-12 di sini yang TIDAK muncul di seed
    data `workers[]` pada module digital_twin_ingestion (yang hanya berisi
    wrk-01 s/d wrk-10) -- menandakan proofing & baking punya tim tambahan
    (2 worker per stasiun) yang belum di-seed di tabel `workers`. Perlu
    dipastikan FK worker_id -> workers.worker_id konsisten sebelum insert,
    atau data workers perlu ditambah wrk-11 & wrk-12 dulu.

    Cardinality: idealnya 1 row per worker (default multiplier=1.0 bila
    belum di-tuning secara eksplisit).
    """
    __tablename__ = "worker_throughput_multipliers"

    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.worker_id", ondelete="CASCADE"), primary_key=True)
    multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SimulationSeedAssignment(Base):
    """
    Penugasan worker -> job -> asset yang diedit admin.
    `realtime_metrics` BUKAN sumber kebenaran -- itu cache hasil kalkulasi
    terakhir dari service (fatigue/stress/throughput formula, sama seperti
    generate_full_compatibility_matrix di module digital_twin_ingestion).
    Dihitung ulang tiap kali simulasi start; kolom ini cuma buat audit/preview
    di admin panel tanpa perlu re-run kalkulasi.

    Data ini tidak punya seed statis di constants.py (tidak ada dict
    WORKER->JOB->ASSET eksplisit di file ini); assignment dibuat/diedit lewat
    admin panel, dengan `assigned_job_id`/`assigned_asset_id` merujuk ke
    job_desks & assets pada module digital_twin_ingestion (job-01..job-10,
    ast-01..ast-10), sedangkan `WORKER_THROUGHPUT_MULTIPLIER` di atas
    mengisyaratkan job baking & proofing bisa punya >1 worker sekaligus
    (unique constraint (factory_id, worker_id) di sini hanya menjamin
    1 assignment per worker, bukan 1 worker per job/asset).

        realtime_metrics_cache (JSONB, nullable):
            {
                "current_fatigue_level": 0.62,
                "current_stress_level": 0.48,
                "effective_throughput_per_hour": 205.0,
                "effective_error_probability": 0.03,
                "burnout_hazard_risk": 0.15,
                "throughput_multiplier": 1.15   (nilai runtime, bisa berbeda
                    dari WorkerThroughputMultiplier.multiplier statis di atas
                    karena sudah dipengaruhi fatigue/stress saat itu)
            }

    Cardinality: maksimal 1 row per (factory_id, worker_id) -- satu worker
    hanya boleh punya satu assignment aktif per factory.
    """
    __tablename__ = "simulation_seed_assignments"
    __table_args__ = (UniqueConstraint("factory_id", "worker_id", name="uq_simulation_seed_factory_worker"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), nullable=False, index=True)
    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.worker_id", ondelete="CASCADE"), nullable=False)
    assigned_job_id: Mapped[str] = mapped_column(ForeignKey("job_desks.job_id", ondelete="RESTRICT"), nullable=False)
    assigned_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id", ondelete="RESTRICT"), nullable=False)

    # { current_fatigue_level, current_stress_level, effective_throughput_per_hour,
    #   effective_error_probability, burnout_hazard_risk, throughput_multiplier }
    realtime_metrics_cache: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())