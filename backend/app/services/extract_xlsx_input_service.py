from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

import pandas as pd


class UnsupportedWorkbookError(ValueError):
    pass


TERMINAL_TOKENS = {"finished", "finish", "selesai", "end", "done", "keluar", "output"}

MAIN_LANE_TOKENS = {"main", "utama", "inti", "core", "-"}

AUTOMATION_LEVELS = {
    "manual": "manual",
    "manual penuh": "manual",
    "tidak": "manual",
    "no": "manual",
    "semi otomatis": "semi_automated",
    "semi automatic": "semi_automated",
    "semi automated": "semi_automated",
    "semi": "semi_automated",
    "otomatis": "automated",
    "otomatis penuh": "automated",
    "full otomatis": "automated",
    "automatic": "automated",
    "automated": "automated",
    "ya": "automated",
    "yes": "automated",
}

FLOW_TYPES = {
    "batch": "batch",
    "per batch": "batch",
    "kontinu": "continuous",
    "kontinyu": "continuous",
    "continuous": "continuous",
    "continu": "continuous",
    "flow": "continuous",
}

UNIT_CANON = {
    "kg": ("mass", "kg", 1.0),
    "kilogram": ("mass", "kg", 1.0),
    "g": ("mass", "kg", 0.001),
    "gram": ("mass", "kg", 0.001),
    "ton": ("mass", "kg", 1000.0),
    "l": ("volume", "L", 1.0),
    "liter": ("volume", "L", 1.0),
    "ltr": ("volume", "L", 1.0),
    "ml": ("volume", "L", 0.001),
    "pcs": ("count", "pcs", 1.0),
    "pc": ("count", "pcs", 1.0),
    "piece": ("count", "pcs", 1.0),
    "buah": ("count", "pcs", 1.0),
    "unit": ("count", "pcs", 1.0),
    "box": ("count", "box", 1.0),
    "loyang": ("count", "loyang", 1.0),
    "w": ("power", "W", 1.0),
    "watt": ("power", "W", 1.0),
    "kw": ("power", "W", 1000.0),
    "db": ("noise", "dB", 1.0),
    "dba": ("noise", "dB", 1.0),
}

BASIS_SECONDS = {
    "jam": 3600.0,
    "hour": 3600.0,
    "hr": 3600.0,
    "h": 3600.0,
    "menit": 60.0,
    "mnt": 60.0,
    "min": 60.0,
    "minute": 60.0,
    "m": 60.0,
    "detik": 1.0,
    "second": 1.0,
    "sec": 1.0,
    "s": 1.0,
}

BASIS_CYCLE = {"batch", "siklus", "cycle", "loyang", "rak", "trolley", "run"}

QUANTITY_PATTERN = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>[A-Za-z]+)?\s*(?:/\s*(?P<basis>[A-Za-z]+))?"
)

TIME_WINDOW_PATTERN = re.compile(
    r"(?P<start_h>\d{1,2})[.:](?P<start_m>\d{2})\s*[-–—s/d]+\s*(?P<end_h>\d{1,2})[.:](?P<end_m>\d{2})"
)

PARENTHETICAL = re.compile(r"\(([^)]*)\)")

MATERIAL_SPLIT = re.compile(r"\s*(?:\||&|,|;|\+|\bdan\b)\s*", re.IGNORECASE)

BATCH_SPLIT = re.compile(r"\s*(?:\||;)\s*")


def normalize(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = PARENTHETICAL.sub(" ", text)
    text = text.lower().replace("&", " dan ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).replace("\u00a0", " ").replace("\u00ad", "")
    return re.sub(r"\s+", " ", text).strip()


def as_id(value: Any) -> str:
    text = clean_cell(value)
    if not text:
        return ""
    return text.upper()


def as_int(value: Any) -> Optional[int]:
    text = clean_cell(value)
    if not text:
        return None
    digits = re.search(r"-?\d+", text.replace(".", "").replace(",", ""))
    return int(digits.group(0)) if digits else None


def as_float(value: Any) -> Optional[float]:
    text = clean_cell(value)
    if not text:
        return None
    digits = re.search(r"-?\d+(?:[.,]\d+)?", text.replace(".", ""))
    if not digits:
        return None
    return float(digits.group(0).replace(",", "."))


@dataclass
class Quantity:
    raw: str
    value: Optional[float] = None
    unit: Optional[str] = None
    unit_class: Optional[str] = None
    basis: Optional[str] = None
    basis_seconds: Optional[float] = None
    per_cycle: bool = False

    @property
    def is_parsed(self) -> bool:
        return self.value is not None

    def per_hour(self, cycle_seconds: Optional[float] = None) -> Optional[float]:
        if self.value is None:
            return None
        if self.basis_seconds:
            return self.value * (3600.0 / self.basis_seconds)
        if self.per_cycle:
            if not cycle_seconds:
                return None
            return self.value * (3600.0 / cycle_seconds)
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "raw": self.raw,
            "value": self.value,
            "unit": self.unit,
            "unit_class": self.unit_class,
            "basis": self.basis,
        }


def parse_quantity(text: Any) -> Quantity:
    raw = clean_cell(text)
    quantity = Quantity(raw=raw)
    if not raw:
        return quantity
    found = QUANTITY_PATTERN.search(raw)
    if not found:
        return quantity
    quantity.value = float(found.group("value").replace(",", "."))
    unit_token = normalize(found.group("unit"))
    if unit_token in UNIT_CANON:
        unit_class, canonical, factor = UNIT_CANON[unit_token]
        quantity.unit_class = unit_class
        quantity.unit = canonical
        quantity.value *= factor
    elif unit_token:
        quantity.unit = found.group("unit")
    basis_token = normalize(found.group("basis"))
    if basis_token:
        quantity.basis = basis_token
        if basis_token in BASIS_SECONDS:
            quantity.basis_seconds = BASIS_SECONDS[basis_token]
        elif basis_token in BASIS_CYCLE:
            quantity.per_cycle = True
    return quantity


def parse_quantities(text: Any) -> list[Quantity]:
    raw = clean_cell(text)
    if not raw:
        return []
    return [parse_quantity(chunk) for chunk in BATCH_SPLIT.split(raw) if clean_cell(chunk)]


def parse_duration_seconds(text: Any) -> Optional[float]:
    raw = clean_cell(text)
    if not raw:
        return None
    total = 0.0
    matched = False
    for found in QUANTITY_PATTERN.finditer(raw):
        unit_token = normalize(found.group("unit"))
        if unit_token not in BASIS_SECONDS:
            continue
        total += float(found.group("value").replace(",", ".")) * BASIS_SECONDS[unit_token]
        matched = True
    return total if matched else None


def parse_material_list(text: Any) -> list[str]:
    raw = clean_cell(text)
    if not raw:
        return []
    parts = [clean_cell(part) for part in MATERIAL_SPLIT.split(raw)]
    return [part for part in parts if part]


def parse_environment(text: Any) -> dict[str, Any]:
    raw = clean_cell(text)
    result: dict[str, Any] = {"raw": raw, "power_consumption_watt": None, "noise_level_db": None}
    for found in QUANTITY_PATTERN.finditer(raw):
        unit_token = normalize(found.group("unit"))
        if unit_token not in UNIT_CANON:
            continue
        unit_class, _, factor = UNIT_CANON[unit_token]
        value = float(found.group("value").replace(",", ".")) * factor
        if unit_class == "power" and result["power_consumption_watt"] is None:
            result["power_consumption_watt"] = value
        elif unit_class == "noise" and result["noise_level_db"] is None:
            result["noise_level_db"] = value
    return result


def parse_time_window(text: Any) -> dict[str, Any]:
    raw = clean_cell(text)
    result: dict[str, Any] = {"raw": raw, "start_time": None, "end_time": None, "duration_hours": None}
    found = TIME_WINDOW_PATTERN.search(raw)
    if not found:
        return result
    start = int(found.group("start_h")) * 60 + int(found.group("start_m"))
    end = int(found.group("end_h")) * 60 + int(found.group("end_m"))
    if start >= 24 * 60 or end >= 24 * 60:
        return result
    span = end - start
    if span <= 0:
        span += 24 * 60
    result["start_time"] = f"{start // 60:02d}:{start % 60:02d}"
    result["end_time"] = f"{end // 60:02d}:{end % 60:02d}"
    result["duration_hours"] = round(span / 60.0, 2)
    result["crosses_midnight"] = end <= start
    return result


def normalize_automation(text: Any) -> Optional[str]:
    token = normalize(text)
    if not token:
        return None
    if token in AUTOMATION_LEVELS:
        return AUTOMATION_LEVELS[token]
    for alias, level in AUTOMATION_LEVELS.items():
        if alias in token:
            return level
    return None


def normalize_flow_type(text: Any) -> Optional[str]:
    token = normalize(text)
    if not token:
        return None
    if token in FLOW_TYPES:
        return FLOW_TYPES[token]
    for alias, flow in FLOW_TYPES.items():
        if alias in token:
            return flow
    return None


def is_terminal_token(text: Any) -> bool:
    token = normalize(text)
    return bool(token) and token in TERMINAL_TOKENS


COLUMN_ALIASES: dict[str, dict[str, list[str]]] = {
    "stages": {
        "stage_id": ["tahap id", "id tahap", "kode tahap", "stage id", "step id"],
        "lane": ["jalur paralel", "jalur", "lane", "parallel lane", "cabang"],
        "next_stage_id": ["next tahap id", "tahap berikutnya", "tahap selanjutnya", "next stage id",
                          "next step id", "successor"],
        "stage_name": ["tahap proses", "nama tahap", "nama proses", "process stage", "workflow step"],
        "asset_id": ["aset id", "asset id", "id aset", "kode aset"],
        "operator_task": ["deskripsi tugas operator", "deskripsi tugas", "tugas operator",
                          "operator task description", "uraian tugas"],
        "material_input": ["material input utama", "material input", "bahan baku masuk", "input material"],
        "material_output": ["material output utama", "material output", "hasil keluaran", "output material"],
        "material_per_batch": ["kebutuhan material per batch", "kebutuhan material", "material per batch",
                               "takaran per batch"],
        "flow_type": ["tipe aliran proses", "tipe aliran", "jenis aliran", "flow type"],
        "cycle_time": ["waktu siklus standar", "waktu siklus", "cycle time", "standard cycle time"],
        "throughput": ["throughput estimasi", "throughput", "laju produksi", "kapasitas per jam"],
        "automation": ["tingkat otomatisasi", "otomatisasi", "otomasi", "automation level", "automation"],
        "qc": ["quality control", "pengendalian mutu", "kendali mutu", "qc"],
    },
    "allocations": {
        "allocation_id": ["alokasi id", "allocation id", "id alokasi"],
        "stage_id": ["tahap id", "id tahap", "kode tahap", "stage id"],
        "worker_id": ["worker id", "pekerja id", "id pekerja", "kode pekerja"],
        "shift_id": ["shift id", "id shift", "kode shift"],
        "worker_count": ["jumlah pekerja", "jumlah operator", "jumlah tenaga kerja", "headcount"],
        "note": ["keterangan penugasan", "catatan penugasan", "keterangan", "assignment note"],
    },
    "assets": {
        "asset_id": ["aset id", "asset id", "id aset", "kode aset"],
        "asset_name": ["nama peralatan", "nama aset", "nama mesin", "peralatan", "equipment name"],
        "units": ["jumlah unit", "jumlah alat", "banyak unit", "unit count"],
        "capacity_per_unit": ["kapasitas per unit", "capacity per unit", "kapasitas unit"],
        "total_capacity": ["total kapasitas tahap", "total kapasitas", "kapasitas total", "total capacity"],
        "automation": ["tingkat otomatisasi", "otomatisasi", "otomasi", "automation level", "automation"],
        "cost_per_hour": ["biaya operasional per jam", "biaya operasional", "biaya per jam",
                          "operational cost per hour"],
        "environment": ["konsumsi daya faktor lingkungan", "konsumsi daya", "faktor lingkungan",
                        "daya dan lingkungan", "power and environment"],
    },
    "workers": {
        "worker_id": ["worker id", "pekerja id", "id pekerja", "kode pekerja"],
        "worker_name": ["nama pekerja", "nama karyawan", "nama operator", "worker name", "nama"],
    },
    "shifts": {
        "shift_id": ["shift id", "id shift", "kode shift"],
        "shift_hours": ["jam shift", "jam kerja", "waktu shift", "shift hours", "rentang jam"],
    },
}

SHEET_SIGNATURES: dict[str, tuple[set[str], set[str]]] = {
    "stages": ({"stage_id", "stage_name"}, {"asset_id", "next_stage_id", "lane", "qc", "operator_task"}),
    "allocations": ({"allocation_id", "worker_id"}, {"stage_id", "shift_id", "worker_count", "note"}),
    "assets": ({"asset_id", "asset_name"}, {"units", "capacity_per_unit", "total_capacity", "cost_per_hour"}),
    "workers": ({"worker_id", "worker_name"}, set()),
    "shifts": ({"shift_id", "shift_hours"}, set()),
}

SHEET_LABELS = {
    "stages": "Tabel 1 - Tahapan Proses",
    "allocations": "Tabel 2 - Alokasi Pekerja",
    "assets": "Tabel 3 - Daftar Aset",
    "workers": "Tabel 4 - Daftar Pekerja",
    "shifts": "Tabel 5 - Daftar Shift",
}

REQUIRED_SHEETS = ["stages", "allocations", "assets", "workers", "shifts"]

REQUIRED_CELLS: dict[str, list[str]] = {
    "stages": ["stage_id", "stage_name", "asset_id", "next_stage_id", "operator_task",
               "flow_type", "cycle_time", "throughput", "automation"],
    "allocations": ["allocation_id", "stage_id", "worker_id", "shift_id", "worker_count"],
    "assets": ["asset_id", "asset_name", "units", "capacity_per_unit", "total_capacity",
               "automation", "cost_per_hour", "environment"],
    "workers": ["worker_id", "worker_name"],
    "shifts": ["shift_id", "shift_hours"],
}

FIRST_DATA_ROW = 2


def match_column(header: Any, sheet_key: str) -> Optional[str]:
    token = normalize(header)
    if not token:
        return None
    best: Optional[tuple[int, str]] = None
    for canonical, aliases in COLUMN_ALIASES[sheet_key].items():
        for alias in aliases:
            if alias in token and (best is None or len(alias) > best[0]):
                best = (len(alias), canonical)
    return best[1] if best else None


def score_sheet(headers: Sequence[Any], sheet_key: str) -> int:
    required, optional = SHEET_SIGNATURES[sheet_key]
    matched = {match_column(header, sheet_key) for header in headers}
    matched.discard(None)
    if not required.issubset(matched):
        return 0
    return len(required) * 10 + len(matched & optional)


@dataclass
class SheetFrame:
    key: str
    source_name: str
    columns: dict[str, str]
    rows: list[dict[str, str]]
    unmapped_headers: list[str]

    def missing_columns(self) -> list[str]:
        return [name for name in REQUIRED_CELLS[self.key] if name not in self.columns]

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


@dataclass
class RawWorkbook:
    source_name: str
    sheets: dict[str, SheetFrame] = field(default_factory=dict)
    unidentified_sheets: list[str] = field(default_factory=list)

    def missing_sheets(self) -> list[str]:
        return [key for key in REQUIRED_SHEETS if key not in self.sheets]

    def cell(self, sheet_key: str, excel_row: int, column: str) -> Optional[str]:
        sheet = self.sheets.get(sheet_key)
        if sheet is None:
            return None
        for row in sheet.rows:
            if row["_row"] == excel_row:
                return row.get(column)
        return None

    def set_cell(self, sheet_key: str, excel_row: int, column: str, value: str) -> bool:
        sheet = self.sheets.get(sheet_key)
        if sheet is None or column not in COLUMN_ALIASES[sheet_key]:
            return False
        for row in sheet.rows:
            if row["_row"] == excel_row:
                row[column] = clean_cell(value)
                sheet.columns.setdefault(column, column)
                return True
        return False


def read_workbook(path: str | Path) -> RawWorkbook:
    resolved = Path(path)
    if resolved.suffix.lower() not in {".xlsx", ".xlsm"}:
        raise UnsupportedWorkbookError(
            f"Format tidak didukung: '{resolved.suffix}'. Gunakan berkas .xlsx atau .xlsm."
        )

    excel = pd.ExcelFile(resolved)
    workbook = RawWorkbook(source_name=resolved.name)
    claimed: dict[str, tuple[int, str]] = {}

    for sheet_name in excel.sheet_names:
        frame = excel.parse(sheet_name, header=0, dtype=object)
        frame = frame.dropna(how="all")
        if frame.empty:
            continue
        headers = list(frame.columns)
        scores = {key: score_sheet(headers, key) for key in REQUIRED_SHEETS}
        best_key = max(scores, key=lambda key: scores[key])
        if scores[best_key] == 0:
            workbook.unidentified_sheets.append(sheet_name)
            continue
        if best_key in claimed and claimed[best_key][0] >= scores[best_key]:
            workbook.unidentified_sheets.append(sheet_name)
            continue
        claimed[best_key] = (scores[best_key], sheet_name)
        workbook.sheets[best_key] = _build_sheet_frame(best_key, sheet_name, frame)

    return workbook


def _build_sheet_frame(sheet_key: str, sheet_name: str, frame: pd.DataFrame) -> SheetFrame:
    columns: dict[str, str] = {}
    unmapped: list[str] = []
    for header in frame.columns:
        canonical = match_column(header, sheet_key)
        if canonical and canonical not in columns:
            columns[canonical] = str(header)
        else:
            unmapped.append(str(header))

    rows: list[dict[str, str]] = []
    for offset, (_, record) in enumerate(frame.iterrows()):
        row: dict[str, str] = {"_row": FIRST_DATA_ROW + offset}
        for canonical, header in columns.items():
            row[canonical] = clean_cell(record[header])
        if any(value for key, value in row.items() if key != "_row"):
            rows.append(row)

    return SheetFrame(
        key=sheet_key,
        source_name=sheet_name,
        columns=columns,
        rows=rows,
        unmapped_headers=unmapped,
    )


@dataclass
class StageRecord:
    excel_row: int
    stage_id: str
    lane: str
    next_stage_id: Optional[str]
    is_terminal: bool
    stage_name: str
    asset_id: str
    operator_task: str
    material_input: list[str]
    material_output: list[str]
    material_per_batch: list[Quantity]
    flow_type: Optional[str]
    cycle_time_seconds: Optional[float]
    throughput: Quantity
    throughput_per_hour: Optional[float]
    automation_level: Optional[str]
    qc_requirement: str
    raw: dict[str, str]


@dataclass
class AssetRecord:
    excel_row: int
    asset_id: str
    asset_name: str
    units_available: Optional[int]
    capacity_per_unit: Quantity
    total_capacity: Quantity
    automation_level: Optional[str]
    operational_cost_per_hour: Optional[float]
    power_consumption_watt: Optional[float]
    noise_level_db: Optional[float]
    raw: dict[str, str]


@dataclass
class AllocationRecord:
    excel_row: int
    allocation_id: str
    stage_id: str
    worker_ids: list[str]
    shift_id: str
    declared_worker_count: Optional[int]
    note: str
    raw: dict[str, str]


@dataclass
class WorkerRecord:
    excel_row: int
    worker_id: str
    worker_name: str
    raw: dict[str, str]


@dataclass
class ShiftRecord:
    excel_row: int
    shift_id: str
    start_time: Optional[str]
    end_time: Optional[str]
    duration_hours: Optional[float]
    crosses_midnight: bool
    raw: dict[str, str]


@dataclass
class ProcessGraph:
    order: list[str] = field(default_factory=list)
    depth: dict[str, int] = field(default_factory=dict)
    edges: list[dict[str, str]] = field(default_factory=list)
    entry_stages: list[str] = field(default_factory=list)
    terminal_stages: list[str] = field(default_factory=list)
    parallel_groups: list[dict[str, Any]] = field(default_factory=list)
    lanes: list[str] = field(default_factory=list)
    cycles: list[list[str]] = field(default_factory=list)
    unreachable_stages: list[str] = field(default_factory=list)
    dangling_edges: list[dict[str, str]] = field(default_factory=list)

    @property
    def process_type(self) -> str:
        if self.cycles:
            return "hybrid"
        if self.parallel_groups:
            return "hybrid" if len(self.order) > sum(len(g["steps"]) for g in self.parallel_groups) else "parallel"
        return "serial"


@dataclass
class FactoryWorkbook:
    source_name: str
    raw: RawWorkbook
    stages: list[StageRecord] = field(default_factory=list)
    assets: list[AssetRecord] = field(default_factory=list)
    allocations: list[AllocationRecord] = field(default_factory=list)
    workers: list[WorkerRecord] = field(default_factory=list)
    shifts: list[ShiftRecord] = field(default_factory=list)
    graph: ProcessGraph = field(default_factory=ProcessGraph)

    def stage_by_id(self, stage_id: str) -> Optional[StageRecord]:
        return next((stage for stage in self.stages if stage.stage_id == stage_id), None)

    def asset_by_id(self, asset_id: str) -> Optional[AssetRecord]:
        return next((asset for asset in self.assets if asset.asset_id == asset_id), None)

    def shift_by_id(self, shift_id: str) -> Optional[ShiftRecord]:
        return next((shift for shift in self.shifts if shift.shift_id == shift_id), None)

    def allocations_for_stage(self, stage_id: str) -> list[AllocationRecord]:
        return [item for item in self.allocations if item.stage_id == stage_id]

    def declared_worker_count(self) -> int:
        return sum(item.declared_worker_count or 0 for item in self.allocations)


def _split_ids(text: Any) -> list[str]:
    raw = clean_cell(text)
    if not raw:
        return []
    return [as_id(part) for part in MATERIAL_SPLIT.split(raw) if clean_cell(part)]


def build_stage(row: dict[str, str]) -> StageRecord:
    cycle_seconds = parse_duration_seconds(row.get("cycle_time"))
    throughput = parse_quantity(row.get("throughput"))
    next_raw = row.get("next_stage_id", "")
    terminal = is_terminal_token(next_raw)
    return StageRecord(
        excel_row=row["_row"],
        stage_id=as_id(row.get("stage_id")),
        lane=clean_cell(row.get("lane")),
        next_stage_id=None if terminal else as_id(next_raw) or None,
        is_terminal=terminal,
        stage_name=clean_cell(row.get("stage_name")),
        asset_id=as_id(row.get("asset_id")),
        operator_task=clean_cell(row.get("operator_task")),
        material_input=parse_material_list(row.get("material_input")),
        material_output=parse_material_list(row.get("material_output")),
        material_per_batch=parse_quantities(row.get("material_per_batch")),
        flow_type=normalize_flow_type(row.get("flow_type")),
        cycle_time_seconds=cycle_seconds,
        throughput=throughput,
        throughput_per_hour=throughput.per_hour(cycle_seconds),
        automation_level=normalize_automation(row.get("automation")),
        qc_requirement=clean_cell(row.get("qc")),
        raw=row,
    )


def build_asset(row: dict[str, str]) -> AssetRecord:
    environment = parse_environment(row.get("environment"))
    return AssetRecord(
        excel_row=row["_row"],
        asset_id=as_id(row.get("asset_id")),
        asset_name=clean_cell(row.get("asset_name")),
        units_available=as_int(row.get("units")),
        capacity_per_unit=parse_quantity(row.get("capacity_per_unit")),
        total_capacity=parse_quantity(row.get("total_capacity")),
        automation_level=normalize_automation(row.get("automation")),
        operational_cost_per_hour=as_float(row.get("cost_per_hour")),
        power_consumption_watt=environment["power_consumption_watt"],
        noise_level_db=environment["noise_level_db"],
        raw=row,
    )


def build_allocation(row: dict[str, str]) -> AllocationRecord:
    return AllocationRecord(
        excel_row=row["_row"],
        allocation_id=as_id(row.get("allocation_id")),
        stage_id=as_id(row.get("stage_id")),
        worker_ids=_split_ids(row.get("worker_id")),
        shift_id=as_id(row.get("shift_id")),
        declared_worker_count=as_int(row.get("worker_count")),
        note=clean_cell(row.get("note")),
        raw=row,
    )


def build_worker(row: dict[str, str]) -> WorkerRecord:
    return WorkerRecord(
        excel_row=row["_row"],
        worker_id=as_id(row.get("worker_id")),
        worker_name=clean_cell(row.get("worker_name")),
        raw=row,
    )


def build_shift(row: dict[str, str]) -> ShiftRecord:
    window = parse_time_window(row.get("shift_hours"))
    return ShiftRecord(
        excel_row=row["_row"],
        shift_id=as_id(row.get("shift_id")),
        start_time=window["start_time"],
        end_time=window["end_time"],
        duration_hours=window["duration_hours"],
        crosses_midnight=bool(window.get("crosses_midnight")),
        raw=row,
    )


def build_graph(stages: Sequence[StageRecord]) -> ProcessGraph:
    graph = ProcessGraph()
    known = {stage.stage_id for stage in stages}
    successors: dict[str, list[str]] = defaultdict(list)
    indegree: dict[str, int] = {stage.stage_id: 0 for stage in stages}

    for stage in stages:
        if stage.is_terminal or not stage.next_stage_id:
            graph.terminal_stages.append(stage.stage_id)
            continue
        target = stage.next_stage_id
        graph.edges.append({"from": stage.stage_id, "to": target})
        if target not in known:
            graph.dangling_edges.append({"from": stage.stage_id, "to": target})
            continue
        successors[stage.stage_id].append(target)
        indegree[target] += 1

    graph.entry_stages = [stage.stage_id for stage in stages if indegree[stage.stage_id] == 0]
    graph.lanes = sorted({stage.lane for stage in stages if stage.lane and normalize(stage.lane) not in MAIN_LANE_TOKENS})

    queue = deque(graph.entry_stages)
    depth = {stage_id: 0 for stage_id in graph.entry_stages}
    remaining = dict(indegree)
    while queue:
        current = queue.popleft()
        graph.order.append(current)
        for target in successors[current]:
            depth[target] = max(depth.get(target, 0), depth[current] + 1)
            remaining[target] -= 1
            if remaining[target] == 0:
                queue.append(target)

    graph.depth = depth
    pending = [stage_id for stage_id, value in remaining.items() if value > 0]
    if pending:
        graph.cycles.append(sorted(pending))
    graph.unreachable_stages = [
        stage.stage_id for stage in stages if stage.stage_id not in graph.order and stage.stage_id not in pending
    ]

    grouped: dict[tuple[int, str], list[str]] = defaultdict(list)
    for stage in stages:
        if stage.stage_id not in depth:
            continue
        key = (depth[stage.stage_id], stage.next_stage_id or "__terminal__")
        grouped[key].append(stage.stage_id)

    index = 0
    for (level, target), members in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        if len(members) < 2:
            continue
        index += 1
        lanes = sorted({stage.lane for stage in stages if stage.stage_id in members and stage.lane})
        graph.parallel_groups.append({
            "group_id": f"pg-{index:02d}",
            "depth": level,
            "steps": sorted(members),
            "lanes": lanes,
            "converges_to": None if target == "__terminal__" else target,
        })

    return graph


def build_workbook(raw: RawWorkbook) -> FactoryWorkbook:
    workbook = FactoryWorkbook(source_name=raw.source_name, raw=raw)
    builders = {
        "stages": (build_stage, "stages"),
        "assets": (build_asset, "assets"),
        "allocations": (build_allocation, "allocations"),
        "workers": (build_worker, "workers"),
        "shifts": (build_shift, "shifts"),
    }
    for sheet_key, (builder, attribute) in builders.items():
        sheet = raw.sheets.get(sheet_key)
        if sheet is None:
            continue
        setattr(workbook, attribute, [builder(row) for row in sheet.rows])

    workbook.graph = build_graph(workbook.stages)
    return workbook


def extract_workbook(path: str | Path) -> FactoryWorkbook:
    return build_workbook(read_workbook(path))


def apply_repairs(raw: RawWorkbook, repairs: dict[str, str]) -> tuple[RawWorkbook, list[str]]:
    rejected: list[str] = []
    for address, value in repairs.items():
        parts = re.split(r"[!.]", address)
        if len(parts) != 3:
            rejected.append(address)
            continue
        sheet_key, row_token, column = parts
        row_number = as_int(row_token)
        if row_number is None or not raw.set_cell(sheet_key, row_number, column, value):
            rejected.append(address)
    return raw, rejected


def _format_quantity(quantity: Quantity) -> str:
    if not quantity.raw:
        return "-"
    return quantity.raw


def _stage_table(workbook: FactoryWorkbook) -> str:
    rows = []
    for stage in workbook.stages:
        rows.append({
            "Tahap_ID": stage.stage_id,
            "Jalur": stage.lane or "-",
            "Next": "FINISHED" if stage.is_terminal else (stage.next_stage_id or "-"),
            "Tahap_Proses": stage.stage_name,
            "Aset_ID": stage.asset_id,
            "Deskripsi_Tugas": stage.operator_task,
            "Material_Input": ", ".join(stage.material_input) or "-",
            "Material_Output": ", ".join(stage.material_output) or "-",
            "Kebutuhan_Per_Batch": ", ".join(item.raw for item in stage.material_per_batch) or "-",
            "Tipe_Aliran": stage.flow_type or "-",
            "Waktu_Siklus_Detik": stage.cycle_time_seconds or "-",
            "Throughput": _format_quantity(stage.throughput),
            "Throughput_per_Jam": round(stage.throughput_per_hour, 2) if stage.throughput_per_hour else "-",
            "Otomatisasi": stage.automation_level or "-",
            "Quality_Control": stage.qc_requirement or "-",
        })
    return pd.DataFrame(rows).to_markdown(index=False)


def _asset_table(workbook: FactoryWorkbook) -> str:
    rows = []
    for asset in workbook.assets:
        rows.append({
            "Aset_ID": asset.asset_id,
            "Nama_Peralatan": asset.asset_name,
            "Jumlah_Unit": asset.units_available if asset.units_available is not None else "-",
            "Kapasitas_per_Unit": _format_quantity(asset.capacity_per_unit),
            "Total_Kapasitas": _format_quantity(asset.total_capacity),
            "Otomatisasi": asset.automation_level or "-",
            "Biaya_per_Jam_IDR": asset.operational_cost_per_hour if asset.operational_cost_per_hour else "-",
            "Daya_Watt": asset.power_consumption_watt or "-",
            "Kebisingan_dB": asset.noise_level_db or "-",
        })
    return pd.DataFrame(rows).to_markdown(index=False)


def _allocation_table(workbook: FactoryWorkbook) -> str:
    rows = []
    for allocation in workbook.allocations:
        names = [
            worker.worker_name
            for worker in workbook.workers
            if worker.worker_id in allocation.worker_ids
        ]
        rows.append({
            "Alokasi_ID": allocation.allocation_id,
            "Tahap_ID": allocation.stage_id,
            "Worker_ID": ", ".join(allocation.worker_ids) or "-",
            "Nama_Pekerja": ", ".join(names) or "-",
            "Shift_ID": allocation.shift_id,
            "Jumlah_Pekerja": allocation.declared_worker_count
            if allocation.declared_worker_count is not None else "-",
            "Keterangan": allocation.note or "-",
        })
    return pd.DataFrame(rows).to_markdown(index=False)


def _shift_table(workbook: FactoryWorkbook) -> str:
    rows = []
    for shift in workbook.shifts:
        rows.append({
            "Shift_ID": shift.shift_id,
            "Mulai": shift.start_time or "-",
            "Selesai": shift.end_time or "-",
            "Durasi_Jam": shift.duration_hours if shift.duration_hours else "-",
            "Lintas_Tengah_Malam": "ya" if shift.crosses_midnight else "tidak",
        })
    return pd.DataFrame(rows).to_markdown(index=False)


def _worker_table(workbook: FactoryWorkbook) -> str:
    rows = [{"Worker_ID": worker.worker_id, "Nama_Pekerja": worker.worker_name} for worker in workbook.workers]
    return pd.DataFrame(rows).to_markdown(index=False)


def build_agent_input(workbook: FactoryWorkbook) -> str:
    graph = workbook.graph
    blocks = [
        f"Sumber data: {workbook.source_name}",
        f"Jenis proses: {graph.process_type}",
        f"Jumlah tahap: {len(workbook.stages)}",
        f"Jumlah pekerja terdaftar: {len(workbook.workers)}",
        f"Total pekerja dideklarasikan pada alokasi: {workbook.declared_worker_count()}",
        f"Tahap awal: {', '.join(graph.entry_stages) or '-'}",
        f"Tahap akhir: {', '.join(graph.terminal_stages) or '-'}",
        f"Urutan topologis: {' -> '.join(graph.order) or '-'}",
        f"Jalur paralel: {', '.join(graph.lanes) or '-'}",
    ]

    for group in graph.parallel_groups:
        target = group["converges_to"] or "FINISHED"
        blocks.append(
            f"Grup paralel {group['group_id']}: {', '.join(group['steps'])} bergabung di {target}"
        )

    blocks.append(f"\nTABEL 1 ({SHEET_LABELS['stages']})\n{_stage_table(workbook)}")
    blocks.append(f"\nTABEL 2 ({SHEET_LABELS['allocations']})\n{_allocation_table(workbook)}")
    blocks.append(f"\nTABEL 3 ({SHEET_LABELS['assets']})\n{_asset_table(workbook)}")
    blocks.append(f"\nTABEL 4 ({SHEET_LABELS['workers']})\n{_worker_table(workbook)}")
    blocks.append(f"\nTABEL 5 ({SHEET_LABELS['shifts']})\n{_shift_table(workbook)}")
    return "\n".join(blocks)


def workbook_as_dict(workbook: FactoryWorkbook) -> dict[str, Any]:
    return {
        "source_name": workbook.source_name,
        "process_graph": {
            "process_type": workbook.graph.process_type,
            "workflow_sequence": workbook.graph.order,
            "edges": workbook.graph.edges,
            "entry_stages": workbook.graph.entry_stages,
            "terminal_stages": workbook.graph.terminal_stages,
            "parallel_groups": workbook.graph.parallel_groups,
            "lanes": workbook.graph.lanes,
        },
        "stages": [
            {
                "stage_id": stage.stage_id,
                "lane": stage.lane,
                "next_stage_id": stage.next_stage_id,
                "is_terminal": stage.is_terminal,
                "stage_name": stage.stage_name,
                "asset_id": stage.asset_id,
                "operator_task": stage.operator_task,
                "material_input": stage.material_input,
                "material_output": stage.material_output,
                "material_per_batch": [item.as_dict() for item in stage.material_per_batch],
                "flow_type": stage.flow_type,
                "cycle_time_seconds": stage.cycle_time_seconds,
                "throughput": stage.throughput.as_dict(),
                "throughput_per_hour": stage.throughput_per_hour,
                "automation_level": stage.automation_level,
                "qc_requirement": stage.qc_requirement,
            }
            for stage in workbook.stages
        ],
        "assets": [
            {
                "asset_id": asset.asset_id,
                "asset_name": asset.asset_name,
                "units_available": asset.units_available,
                "capacity_per_unit": asset.capacity_per_unit.as_dict(),
                "total_capacity": asset.total_capacity.as_dict(),
                "automation_level": asset.automation_level,
                "operational_cost_per_hour": asset.operational_cost_per_hour,
                "power_consumption_watt": asset.power_consumption_watt,
                "noise_level_db": asset.noise_level_db,
            }
            for asset in workbook.assets
        ],
        "allocations": [
            {
                "allocation_id": allocation.allocation_id,
                "stage_id": allocation.stage_id,
                "worker_ids": allocation.worker_ids,
                "shift_id": allocation.shift_id,
                "declared_worker_count": allocation.declared_worker_count,
                "note": allocation.note,
            }
            for allocation in workbook.allocations
        ],
        "workers": [
            {"worker_id": worker.worker_id, "name": worker.worker_name}
            for worker in workbook.workers
        ],
        "shifts": [
            {
                "shift_id": shift.shift_id,
                "start_time": shift.start_time,
                "end_time": shift.end_time,
                "duration_hours": shift.duration_hours,
                "crosses_midnight": shift.crosses_midnight,
            }
            for shift in workbook.shifts
        ],
    }