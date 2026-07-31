"""
Konstanta simulasi pabrik — port langsung dari frontend `simulationApi.mock.ts`.
Single source of truth untuk mass balance, kapasitas, biaya, dan seed worker.

PENTING: kalau kamu ubah resep/kapasitas di sini, cek juga apakah frontend
`simulation.types.ts` / komponen chart butuh disesuaikan (mis. jumlah step = 10).
"""
from typing import TypedDict


class MaterialTemplate(TypedDict):
    name: str
    unit: str


# ---------------------------------------------------------------------------
# Per-station templates & capacity config
# ---------------------------------------------------------------------------

MATERIAL_BY_ORDINAL: dict[int, MaterialTemplate] = {
    1: {"name": "Bahan Baku Tertimbang", "unit": "kg"},
    2: {"name": "Adonan Tercampur", "unit": "kg"},
    3: {"name": "Potongan Adonan", "unit": "pcs"},
    4: {"name": "Adonan Terbentuk", "unit": "pcs"},
    5: {"name": "Loyang Terisi", "unit": "loyang"},
    6: {"name": "Loyang Proofing", "unit": "loyang"},
    7: {"name": "Loyang Panggang", "unit": "loyang"},
    8: {"name": "Produk Mendingin", "unit": "pcs"},
    9: {"name": "Produk Lolos Sortir", "unit": "pcs"},
    10: {"name": "Produk Terkemas", "unit": "pack"},
}

STEP_NAMES: dict[int, str] = {
    1: "Preparation", 2: "Mixing", 3: "Molding", 4: "Fermentation", 5: "Shaping",
    6: "Proofing", 7: "Baking Process", 8: "Cooling", 9: "Sorting", 10: "Packaging",
}

STEP_COST_BASE: dict[int, int] = {
    1: 1_200_000, 2: 1_300_000, 3: 1_150_000, 4: 1_400_000, 5: 1_250_000,
    6: 1_350_000, 7: 2_500_000, 8: 1_100_000, 9: 1_050_000, 10: 1_100_000,
}

CAPACITY_BY_ORDINAL: dict[int, float] = {
    1: 40, 2: 46, 3: 420, 4: 270, 5: 48, 6: 24, 7: 28, 8: 320, 9: 260, 10: 42,
}

# ---------------------------------------------------------------------------
# RECIPE TABLE — single source of truth untuk mass balance
# ---------------------------------------------------------------------------

BATCH_IN_BY_ORDINAL: dict[int, float] = {
    1: 20, 2: 18, 3: 130, 4: 132, 5: 18, 6: 9, 7: 14, 8: 120, 9: 110, 10: 21,
}

BATCH_OUT_BY_ORDINAL: dict[int, float] = {
    1: 19.6, 2: 252, 3: 126, 4: 11, 5: 18, 6: 9, 7: 168, 8: 114, 9: 11, 10: 21,
}

CYCLE_TICKS_BY_ORDINAL: dict[int, int] = {
    1: 2, 2: 2, 3: 1, 4: 1, 5: 3, 6: 4, 7: 5, 8: 1, 9: 1, 10: 2,
}

BOTTLENECK_FILL_THRESHOLD = 0.7
IDLE_QTY_THRESHOLD = 0.05
STATION_1_SAFETY_MARGIN = 0.03

WAREHOUSE_CAPACITY = 4000
WAREHOUSE_FEED_RATE = 9

# HARUS sama persis dengan `WAREHOUSE_STEP_ID` di frontend `simulation.types.ts`
# — cek nilainya di sana dan sesuaikan string di bawah ini kalau berbeda.
WAREHOUSE_STEP_ID = "warehouse"

WORKER_THROUGHPUT_MULTIPLIER: dict[str, float] = {
    "wrk-01": 1.05, "wrk-02": 1.1, "wrk-03": 1.0, "wrk-04": 1.08, "wrk-05": 1.05,
    "wrk-06": 1.0, "wrk-11": 1.04,  # Proofing team (2 workers)
    "wrk-07": 1.15, "wrk-12": 1.10,  # Baking team (2 workers)
    "wrk-08": 0.95, "wrk-09": 1.0, "wrk-10": 1.02,
}

# ---------------------------------------------------------------------------
# Shift & time scheduler
# ---------------------------------------------------------------------------

SHIFT_START_MINUTES = 8 * 60   # 08:00
BREAK_START_ELAPSED = 4 * 60   # 12:00 (240 menit elapsed)
BREAK_END_ELAPSED = 5 * 60     # 13:00 (300 menit elapsed)
SHIFT_END_ELAPSED = 9 * 60     # 17:00 (540 menit elapsed)

INSIGHT = (
    "Simulasi dinamis aktif. Pos dengan multi-worker memiliki kapasitas pemrosesan "
    "lebih tinggi dan menghabiskan material lebih cepat. Saat material di pos kosong, "
    "pekerja akan otomatis beristirahat dan memulihkan fatigue/stress."
)

TARGET_OUTPUT_UNITS = 2500.0