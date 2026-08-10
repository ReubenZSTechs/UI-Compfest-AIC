from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Sequence

from backend.app.services.extract_xlsx_input_service import (
    REQUIRED_CELLS,
    REQUIRED_SHEETS,
    SHEET_LABELS,
    AllocationRecord,
    FactoryWorkbook,
    Quantity,
    StageRecord,
    normalize,
)


class Severity(str, Enum):
    BLOCKING = "blocking"
    WARNING = "warning"
    INFO = "info"


SEVERITY_ORDER = {Severity.BLOCKING: 0, Severity.WARNING: 1, Severity.INFO: 2}

FUNCTION_KEYWORDS: dict[str, set[str]] = {
    "mixing": {"mixer", "aduk", "pengadukan", "mixing", "spiral", "kneader"},
    "cooking": {"cook", "kettle", "masak", "memasak", "boiler", "rebus"},
    "grating": {"grater", "parut", "memarut", "shredder"},
    "shaping": {"shaper", "divider", "rounder", "bentuk", "pembentukan", "moulder", "sheeter"},
    "proofing": {"proofer", "proofing", "fermentasi", "pengembangan"},
    "baking": {"oven", "panggang", "pemanggangan", "baking", "bakar"},
    "cooling": {"cooling", "dingin", "pendinginan", "chiller"},
    "packing": {"packing", "wrapper", "kemas", "pengepakan", "sealer", "packaging"},
}

FIELD_LABELS: dict[str, str] = {
    "stage_id": "Tahap_ID",
    "lane": "Jalur_Paralel",
    "next_stage_id": "Next_Tahap_ID",
    "stage_name": "Tahap_Proses",
    "asset_id": "Aset_ID",
    "operator_task": "Deskripsi_Tugas_Operator",
    "material_input": "Material_Input_Utama",
    "material_output": "Material_Output_Utama",
    "material_per_batch": "Kebutuhan_Material_Per_Batch",
    "flow_type": "Tipe_Aliran_Proses",
    "cycle_time": "Waktu_Siklus_Standar",
    "throughput": "Throughput_Estimasi",
    "automation": "Tingkat_Otomatisasi",
    "qc": "Quality_Control",
    "allocation_id": "Alokasi_ID",
    "worker_id": "Worker_ID",
    "shift_id": "Shift_ID",
    "worker_count": "Jumlah_Pekerja",
    "note": "Keterangan_Penugasan",
    "asset_name": "Nama_Peralatan",
    "units": "Jumlah_Unit",
    "capacity_per_unit": "Kapasitas_per_Unit",
    "total_capacity": "Total_Kapasitas_Tahap",
    "cost_per_hour": "Biaya_Operasional_per_Jam",
    "environment": "Konsumsi_Daya_Faktor_Lingkungan",
    "worker_name": "Nama_Pekerja",
    "shift_hours": "Jam_Shift",
}


@dataclass
class ValidationIssue:
    code: str
    severity: Severity
    sheet_key: Optional[str]
    excel_row: Optional[int]
    column: Optional[str]
    entity_id: Optional[str]
    message: str
    question: str
    observed: Optional[str] = None
    expected: Optional[str] = None

    @property
    def sheet_label(self) -> str:
        return SHEET_LABELS.get(self.sheet_key or "", "Workbook")

    @property
    def repair_address(self) -> Optional[str]:
        if not self.sheet_key or self.excel_row is None or not self.column:
            return None
        return f"{self.sheet_key}!{self.excel_row}.{self.column}"

    @property
    def cell_reference(self) -> str:
        if self.excel_row is None:
            return self.sheet_label
        label = FIELD_LABELS.get(self.column or "", self.column or "-")
        return f"{self.sheet_label}, baris {self.excel_row}, kolom {label}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "sheet": self.sheet_label,
            "row": self.excel_row,
            "column": FIELD_LABELS.get(self.column or "", self.column),
            "entity_id": self.entity_id,
            "message": self.message,
            "question": self.question,
            "observed": self.observed,
            "expected": self.expected,
            "repair_address": self.repair_address,
        }


@dataclass
class ValidationReport:
    source_name: str
    issues: list[ValidationIssue] = field(default_factory=list)

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)

    def by_severity(self, severity: Severity) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity is severity]

    @property
    def blocking(self) -> list[ValidationIssue]:
        return self.by_severity(Severity.BLOCKING)

    @property
    def warnings(self) -> list[ValidationIssue]:
        return self.by_severity(Severity.WARNING)

    @property
    def infos(self) -> list[ValidationIssue]:
        return self.by_severity(Severity.INFO)

    @property
    def blocking_count(self) -> int:
        return len(self.blocking)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def is_complete(self) -> bool:
        return self.blocking_count == 0

    def sorted_issues(self) -> list[ValidationIssue]:
        return sorted(
            self.issues,
            key=lambda issue: (SEVERITY_ORDER[issue.severity], issue.sheet_key or "", issue.excel_row or 0),
        )

    def as_records(self) -> list[dict[str, Any]]:
        return [issue.as_dict() for issue in self.sorted_issues()]

    def repair_addresses(self) -> list[str]:
        return [issue.repair_address for issue in self.sorted_issues() if issue.repair_address]

    def as_prompt_payload(self) -> str:
        payload = {
            "sumber": self.source_name,
            "status": "lengkap" if self.is_complete else "belum lengkap",
            "jumlah_blocking": self.blocking_count,
            "jumlah_warning": self.warning_count,
            "temuan": [
                {
                    "kode": issue.code,
                    "tingkat": issue.severity.value,
                    "lokasi": issue.cell_reference,
                    "alamat_perbaikan": issue.repair_address,
                    "masalah": issue.message,
                    "nilai_terbaca": issue.observed,
                    "nilai_diharapkan": issue.expected,
                    "pertanyaan": issue.question,
                }
                for issue in self.sorted_issues()
                if issue.severity is not Severity.INFO
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)


def _quantity_per_hour(quantity: Quantity, cycle_seconds: Optional[float]) -> Optional[float]:
    return quantity.per_hour(cycle_seconds)


def _function_groups(text: str) -> set[str]:
    words = set(normalize(text).split())
    if not words:
        return set()
    return {group for group, keywords in FUNCTION_KEYWORDS.items() if words & keywords}


def _check_structure(workbook: FactoryWorkbook, report: ValidationReport) -> None:
    for sheet_key in REQUIRED_SHEETS:
        sheet = workbook.raw.sheets.get(sheet_key)
        if sheet is None:
            report.add(ValidationIssue(
                code="STRUCT_SHEET_MISSING",
                severity=Severity.BLOCKING,
                sheet_key=sheet_key,
                excel_row=None,
                column=None,
                entity_id=None,
                message=f"Sheet untuk {SHEET_LABELS[sheet_key]} tidak ditemukan pada workbook.",
                question=f"Workbook belum memuat {SHEET_LABELS[sheet_key]}. "
                         "Bisakah Anda mengunggah ulang berkas dengan sheet tersebut disertakan?",
            ))
            continue

        if not sheet.rows:
            report.add(ValidationIssue(
                code="STRUCT_SHEET_EMPTY",
                severity=Severity.BLOCKING,
                sheet_key=sheet_key,
                excel_row=None,
                column=None,
                entity_id=None,
                message=f"{SHEET_LABELS[sheet_key]} tidak memiliki baris data.",
                question=f"{SHEET_LABELS[sheet_key]} kosong. Data apa yang seharusnya diisi di sheet ini?",
            ))

        for column in sheet.missing_columns():
            label = FIELD_LABELS.get(column, column)
            report.add(ValidationIssue(
                code="STRUCT_COLUMN_MISSING",
                severity=Severity.BLOCKING,
                sheet_key=sheet_key,
                excel_row=None,
                column=column,
                entity_id=None,
                message=f"Kolom wajib '{label}' tidak ditemukan pada {SHEET_LABELS[sheet_key]}.",
                question=f"Kolom '{label}' belum ada di {SHEET_LABELS[sheet_key]}. "
                         "Apa nama kolom penggantinya di berkas Anda, atau perlukah kolom itu ditambahkan?",
            ))


def _check_required_cells(workbook: FactoryWorkbook, report: ValidationReport) -> None:
    for sheet_key in REQUIRED_SHEETS:
        sheet = workbook.raw.sheets.get(sheet_key)
        if sheet is None:
            continue
        for row in sheet.rows:
            for column in REQUIRED_CELLS[sheet_key]:
                if column not in sheet.columns or row.get(column):
                    continue
                label = FIELD_LABELS.get(column, column)
                report.add(ValidationIssue(
                    code="CELL_EMPTY",
                    severity=Severity.BLOCKING,
                    sheet_key=sheet_key,
                    excel_row=row["_row"],
                    column=column,
                    entity_id=row.get(REQUIRED_CELLS[sheet_key][0]),
                    message=f"Sel wajib '{label}' kosong.",
                    observed="(kosong)",
                    question=f"Nilai '{label}' pada {SHEET_LABELS[sheet_key]} baris {row['_row']} masih kosong. "
                             "Berapa atau apa nilai yang benar untuk sel ini?",
                ))


def _check_duplicate_ids(workbook: FactoryWorkbook, report: ValidationReport) -> None:
    registries: list[tuple[str, str, str, Sequence[Any]]] = [
        ("stages", "stage_id", "stage_id", workbook.stages),
        ("assets", "asset_id", "asset_id", workbook.assets),
        ("allocations", "allocation_id", "allocation_id", workbook.allocations),
        ("workers", "worker_id", "worker_id", workbook.workers),
        ("shifts", "shift_id", "shift_id", workbook.shifts),
    ]
    for sheet_key, column, attribute, records in registries:
        seen: dict[str, int] = {}
        for record in records:
            identifier = getattr(record, attribute)
            if not identifier:
                continue
            if identifier in seen:
                report.add(ValidationIssue(
                    code="ID_DUPLICATE",
                    severity=Severity.BLOCKING,
                    sheet_key=sheet_key,
                    excel_row=record.excel_row,
                    column=column,
                    entity_id=identifier,
                    message=f"ID '{identifier}' dipakai lebih dari sekali "
                            f"(baris {seen[identifier]} dan {record.excel_row}).",
                    observed=identifier,
                    question=f"ID '{identifier}' muncul dua kali pada {SHEET_LABELS[sheet_key]}. "
                             f"ID pengganti apa yang harus dipakai untuk baris {record.excel_row}?",
                ))
                continue
            seen[identifier] = record.excel_row


def _check_foreign_keys(workbook: FactoryWorkbook, report: ValidationReport) -> None:
    stage_ids = {stage.stage_id for stage in workbook.stages}
    asset_ids = {asset.asset_id for asset in workbook.assets}
    worker_ids = {worker.worker_id for worker in workbook.workers}
    shift_ids = {shift.shift_id for shift in workbook.shifts}

    for stage in workbook.stages:
        if stage.asset_id and stage.asset_id not in asset_ids:
            report.add(ValidationIssue(
                code="FK_ASSET_MISSING",
                severity=Severity.BLOCKING,
                sheet_key="stages",
                excel_row=stage.excel_row,
                column="asset_id",
                entity_id=stage.stage_id,
                message=f"Tahap '{stage.stage_id}' memakai Aset_ID '{stage.asset_id}' "
                        "yang tidak terdaftar pada tabel aset.",
                observed=stage.asset_id,
                expected=", ".join(sorted(asset_ids)) or "(tabel aset kosong)",
                question=f"Aset '{stage.asset_id}' yang dipakai tahap '{stage.stage_name}' belum ada di "
                         "Tabel 3. Apakah baris aset ini perlu ditambahkan, atau tahap tersebut sebenarnya "
                         "memakai aset lain yang sudah terdaftar?",
            ))
        if not stage.is_terminal and stage.next_stage_id and stage.next_stage_id not in stage_ids:
            report.add(ValidationIssue(
                code="FK_NEXT_STAGE_MISSING",
                severity=Severity.BLOCKING,
                sheet_key="stages",
                excel_row=stage.excel_row,
                column="next_stage_id",
                entity_id=stage.stage_id,
                message=f"Tahap '{stage.stage_id}' menunjuk tahap berikutnya '{stage.next_stage_id}' "
                        "yang tidak ada.",
                observed=stage.next_stage_id,
                expected=", ".join(sorted(stage_ids)) + ", FINISHED",
                question=f"Tahap '{stage.stage_id}' mengarah ke '{stage.next_stage_id}' yang tidak terdaftar. "
                         "Tahap mana yang benar menjadi tujuan berikutnya, atau apakah tahap ini yang terakhir?",
            ))

    for allocation in workbook.allocations:
        if allocation.stage_id and allocation.stage_id not in stage_ids:
            report.add(ValidationIssue(
                code="FK_STAGE_MISSING",
                severity=Severity.BLOCKING,
                sheet_key="allocations",
                excel_row=allocation.excel_row,
                column="stage_id",
                entity_id=allocation.allocation_id,
                message=f"Alokasi '{allocation.allocation_id}' menunjuk tahap "
                        f"'{allocation.stage_id}' yang tidak terdaftar.",
                observed=allocation.stage_id,
                expected=", ".join(sorted(stage_ids)),
                question=f"Alokasi '{allocation.allocation_id}' ditugaskan ke tahap '{allocation.stage_id}' "
                         "yang tidak ada di Tabel 1. Tahap mana yang benar?",
            ))
        for worker_id in allocation.worker_ids:
            if worker_id in worker_ids:
                continue
            report.add(ValidationIssue(
                code="FK_WORKER_MISSING",
                severity=Severity.BLOCKING,
                sheet_key="allocations",
                excel_row=allocation.excel_row,
                column="worker_id",
                entity_id=allocation.allocation_id,
                message=f"Alokasi '{allocation.allocation_id}' menunjuk pekerja '{worker_id}' "
                        "yang tidak terdaftar pada tabel pekerja.",
                observed=worker_id,
                expected=", ".join(sorted(worker_ids)),
                question=f"Pekerja '{worker_id}' belum terdaftar di Tabel 4. Siapa nama pekerja ini, "
                         "atau Worker_ID mana yang seharusnya dipakai?",
            ))
        if allocation.shift_id and allocation.shift_id not in shift_ids:
            report.add(ValidationIssue(
                code="FK_SHIFT_MISSING",
                severity=Severity.BLOCKING,
                sheet_key="allocations",
                excel_row=allocation.excel_row,
                column="shift_id",
                entity_id=allocation.allocation_id,
                message=f"Alokasi '{allocation.allocation_id}' menunjuk shift '{allocation.shift_id}' "
                        "yang tidak terdaftar.",
                observed=allocation.shift_id,
                expected=", ".join(sorted(shift_ids)),
                question=f"Shift '{allocation.shift_id}' tidak ada di Tabel 5. Shift mana yang benar "
                         "untuk alokasi ini?",
            ))


def _check_graph(workbook: FactoryWorkbook, report: ValidationReport) -> None:
    graph = workbook.graph
    if not workbook.stages:
        return

    if not graph.entry_stages:
        report.add(ValidationIssue(
            code="GRAPH_NO_ENTRY",
            severity=Severity.BLOCKING,
            sheet_key="stages",
            excel_row=None,
            column="next_stage_id",
            entity_id=None,
            message="Tidak ada tahap awal: setiap tahap menjadi tujuan tahap lain.",
            question="Alur proses tidak punya titik mulai. Tahap mana yang menjadi tahap pertama?",
        ))

    if not graph.terminal_stages:
        report.add(ValidationIssue(
            code="GRAPH_NO_TERMINAL",
            severity=Severity.BLOCKING,
            sheet_key="stages",
            excel_row=None,
            column="next_stage_id",
            entity_id=None,
            message="Tidak ada tahap akhir: tidak satu pun baris bernilai 'Finished'.",
            question="Alur proses tidak punya titik akhir. Tahap mana yang menghasilkan produk jadi?",
        ))

    for cycle in graph.cycles:
        report.add(ValidationIssue(
            code="GRAPH_CYCLE",
            severity=Severity.BLOCKING,
            sheet_key="stages",
            excel_row=None,
            column="next_stage_id",
            entity_id=None,
            message=f"Alur proses membentuk lingkaran pada tahap: {', '.join(cycle)}.",
            observed=" -> ".join(cycle),
            question=f"Tahap {', '.join(cycle)} saling menunjuk sehingga alur berputar. "
                     "Urutan mana yang benar di antara tahap-tahap tersebut?",
        ))

    for stage_id in graph.unreachable_stages:
        stage = workbook.stage_by_id(stage_id)
        report.add(ValidationIssue(
            code="GRAPH_UNREACHABLE",
            severity=Severity.BLOCKING,
            sheet_key="stages",
            excel_row=stage.excel_row if stage else None,
            column="next_stage_id",
            entity_id=stage_id,
            message=f"Tahap '{stage_id}' tidak terhubung ke alur produksi mana pun.",
            question=f"Tahap '{stage_id}' tidak tersambung ke alur. Tahap mana yang mengalirkan "
                     "material ke tahap ini?",
        ))

    if len(graph.terminal_stages) > 1:
        report.add(ValidationIssue(
            code="GRAPH_MULTI_TERMINAL",
            severity=Severity.WARNING,
            sheet_key="stages",
            excel_row=None,
            column="next_stage_id",
            entity_id=None,
            message=f"Terdapat {len(graph.terminal_stages)} tahap akhir: "
                    f"{', '.join(graph.terminal_stages)}.",
            question="Ada lebih dari satu tahap akhir. Apakah pabrik memang menghasilkan beberapa "
                     "produk jadi terpisah?",
        ))


def _check_coverage(workbook: FactoryWorkbook, report: ValidationReport) -> None:
    allocated_stages = {allocation.stage_id for allocation in workbook.allocations}
    allocated_workers = {
        worker_id for allocation in workbook.allocations for worker_id in allocation.worker_ids
    }
    used_assets = {stage.asset_id for stage in workbook.stages if stage.asset_id}
    used_shifts = {allocation.shift_id for allocation in workbook.allocations if allocation.shift_id}

    for stage in workbook.stages:
        if stage.stage_id in allocated_stages:
            continue
        report.add(ValidationIssue(
            code="STAGE_NO_ALLOCATION",
            severity=Severity.BLOCKING,
            sheet_key="allocations",
            excel_row=None,
            column="stage_id",
            entity_id=stage.stage_id,
            message=f"Tahap '{stage.stage_id}' ({stage.stage_name}) tidak memiliki alokasi pekerja.",
            question=f"Tahap '{stage.stage_name}' belum punya pekerja di Tabel 2. "
                     "Pekerja mana dan pada shift apa yang menangani tahap ini?",
        ))

    for worker in workbook.workers:
        if worker.worker_id in allocated_workers:
            continue
        report.add(ValidationIssue(
            code="WORKER_UNASSIGNED",
            severity=Severity.WARNING,
            sheet_key="workers",
            excel_row=worker.excel_row,
            column="worker_id",
            entity_id=worker.worker_id,
            message=f"Pekerja '{worker.worker_id}' ({worker.worker_name}) tidak ditugaskan ke tahap mana pun.",
            question=f"{worker.worker_name} terdaftar tetapi belum punya penugasan. "
                     "Tahap dan shift mana yang menjadi posnya?",
        ))

    for asset in workbook.assets:
        if asset.asset_id in used_assets:
            continue
        report.add(ValidationIssue(
            code="ASSET_UNUSED",
            severity=Severity.WARNING,
            sheet_key="assets",
            excel_row=asset.excel_row,
            column="asset_id",
            entity_id=asset.asset_id,
            message=f"Aset '{asset.asset_id}' ({asset.asset_name}) tidak dipakai tahap mana pun.",
            question=f"Aset '{asset.asset_name}' tidak terpakai di Tabel 1. "
                     "Tahap mana yang seharusnya memakai aset ini?",
        ))

    for shift in workbook.shifts:
        if shift.shift_id in used_shifts:
            continue
        report.add(ValidationIssue(
            code="SHIFT_UNUSED",
            severity=Severity.INFO,
            sheet_key="shifts",
            excel_row=shift.excel_row,
            column="shift_id",
            entity_id=shift.shift_id,
            message=f"Shift '{shift.shift_id}' terdaftar tetapi tidak dipakai alokasi mana pun.",
            question=f"Shift '{shift.shift_id}' belum dipakai. Apakah shift ini memang tidak aktif "
                     "pada periode simulasi?",
        ))


def _check_headcount(workbook: FactoryWorkbook, report: ValidationReport) -> None:
    row_level = 0
    for allocation in workbook.allocations:
        declared = allocation.declared_worker_count
        listed = len(allocation.worker_ids)
        if declared is None or declared == listed:
            continue
        row_level += 1
        report.add(ValidationIssue(
            code="HEADCOUNT_MISMATCH",
            severity=Severity.BLOCKING,
            sheet_key="allocations",
            excel_row=allocation.excel_row,
            column="worker_id",
            entity_id=allocation.allocation_id,
            message=f"Alokasi '{allocation.allocation_id}' menyatakan {declared} pekerja "
                    f"tetapi hanya mencantumkan {listed} Worker_ID.",
            observed=f"{listed} Worker_ID: {', '.join(allocation.worker_ids) or '(kosong)'}",
            expected=f"{declared} Worker_ID",
            question=f"Alokasi '{allocation.allocation_id}' ({allocation.note}) menuliskan "
                     f"Jumlah_Pekerja {declared}, tetapi Worker_ID yang tercantum hanya {listed}. "
                     "Siapa saja Worker_ID lain yang bertugas di sini, atau apakah Jumlah_Pekerja "
                     "yang perlu dikoreksi?",
        ))

    declared_total = workbook.declared_worker_count()
    registered = len(workbook.workers)
    if not row_level and declared_total and registered and declared_total != registered:
        report.add(ValidationIssue(
            code="ROSTER_MISMATCH",
            severity=Severity.BLOCKING,
            sheet_key="workers",
            excel_row=None,
            column="worker_id",
            entity_id=None,
            message=f"Total Jumlah_Pekerja pada alokasi ({declared_total}) berbeda dengan jumlah "
                    f"pekerja terdaftar ({registered}).",
            observed=str(declared_total),
            expected=str(registered),
            question=f"Tabel 2 mendeklarasikan {declared_total} pekerja sementara Tabel 4 hanya "
                     f"memuat {registered} orang. Apakah ada pekerja yang belum didaftarkan, "
                     "atau angka Jumlah_Pekerja yang perlu diturunkan?",
        ))


def _check_double_booking(workbook: FactoryWorkbook, report: ValidationReport) -> None:
    booking: dict[tuple[str, str], list[AllocationRecord]] = defaultdict(list)
    for allocation in workbook.allocations:
        for worker_id in allocation.worker_ids:
            booking[(worker_id, allocation.shift_id)].append(allocation)

    for (worker_id, shift_id), allocations in booking.items():
        stages = {allocation.stage_id for allocation in allocations}
        if len(stages) < 2:
            continue
        latest = allocations[-1]
        report.add(ValidationIssue(
            code="WORKER_DOUBLE_BOOKED",
            severity=Severity.BLOCKING,
            sheet_key="allocations",
            excel_row=latest.excel_row,
            column="worker_id",
            entity_id=worker_id,
            message=f"Pekerja '{worker_id}' ditugaskan ke {len(stages)} tahap berbeda "
                    f"({', '.join(sorted(stages))}) pada shift yang sama ({shift_id}).",
            observed=", ".join(allocation.allocation_id for allocation in allocations),
            question=f"Pekerja '{worker_id}' tercatat di beberapa tahap sekaligus pada shift {shift_id}. "
                     "Tahap mana yang benar, atau apakah ia memang bergantian antar tahap?",
        ))


def _check_automation_consistency(workbook: FactoryWorkbook, report: ValidationReport) -> None:
    for stage in workbook.stages:
        asset = workbook.asset_by_id(stage.asset_id)
        if asset is None or not stage.automation_level or not asset.automation_level:
            continue
        if stage.automation_level == asset.automation_level:
            continue
        report.add(ValidationIssue(
            code="AUTOMATION_CONFLICT",
            severity=Severity.BLOCKING,
            sheet_key="stages",
            excel_row=stage.excel_row,
            column="automation",
            entity_id=stage.stage_id,
            message=f"Tingkat otomatisasi tahap '{stage.stage_id}' ({stage.raw.get('automation')}) "
                    f"berbeda dengan asetnya '{asset.asset_id}' ({asset.raw.get('automation')}).",
            observed=f"tahap: {stage.raw.get('automation')}",
            expected=f"aset: {asset.raw.get('automation')}",
            question=f"Tahap '{stage.stage_name}' tertulis {stage.raw.get('automation')} sedangkan "
                     f"aset '{asset.asset_name}' tertulis {asset.raw.get('automation')}. "
                     "Mana yang benar untuk dipakai simulasi?",
        ))


def _check_capacity(workbook: FactoryWorkbook, report: ValidationReport) -> None:
    for asset in workbook.assets:
        units = asset.units_available
        per_unit = asset.capacity_per_unit
        total = asset.total_capacity
        if not units or not per_unit.is_parsed or not total.is_parsed:
            continue
        if per_unit.unit_class != total.unit_class:
            report.add(ValidationIssue(
                code="CAPACITY_UNIT_MISMATCH",
                severity=Severity.WARNING,
                sheet_key="assets",
                excel_row=asset.excel_row,
                column="total_capacity",
                entity_id=asset.asset_id,
                message=f"Satuan Kapasitas_per_Unit ({per_unit.raw}) dan Total_Kapasitas_Tahap "
                        f"({total.raw}) pada aset '{asset.asset_id}' tidak sejenis.",
                observed=total.raw,
                expected=per_unit.raw,
                question=f"Aset '{asset.asset_name}' memakai satuan berbeda antara kapasitas per unit "
                         "dan total kapasitas. Satuan mana yang benar?",
            ))
            continue
        expected_total = units * per_unit.value
        if abs(expected_total - total.value) < 1e-6:
            continue
        report.add(ValidationIssue(
            code="CAPACITY_ARITHMETIC",
            severity=Severity.WARNING,
            sheet_key="assets",
            excel_row=asset.excel_row,
            column="total_capacity",
            entity_id=asset.asset_id,
            message=f"Aset '{asset.asset_id}' punya {units} unit x {per_unit.raw} "
                    f"= {expected_total:g}, tetapi Total_Kapasitas_Tahap tertulis {total.raw}.",
            observed=total.raw,
            expected=f"{expected_total:g} {total.unit or ''}".strip(),
            question=f"Total kapasitas '{asset.asset_name}' tidak sama dengan jumlah unit dikali "
                     f"kapasitas per unit. Apakah hanya satu unit yang beroperasi, "
                     "atau angka totalnya yang perlu dikoreksi?",
        ))


def _check_stage_capacity(workbook: FactoryWorkbook, report: ValidationReport) -> None:
    for stage in workbook.stages:
        asset = workbook.asset_by_id(stage.asset_id)
        if asset is None or stage.throughput_per_hour is None:
            continue
        asset_per_hour = _quantity_per_hour(asset.total_capacity, stage.cycle_time_seconds)
        if asset_per_hour is None:
            continue
        if stage.throughput.unit_class != asset.total_capacity.unit_class:
            report.add(ValidationIssue(
                code="THROUGHPUT_UNIT_MISMATCH",
                severity=Severity.WARNING,
                sheet_key="stages",
                excel_row=stage.excel_row,
                column="throughput",
                entity_id=stage.stage_id,
                message=f"Throughput tahap '{stage.stage_id}' ({stage.throughput.raw}) tidak sejenis "
                        f"dengan kapasitas aset '{asset.asset_id}' ({asset.total_capacity.raw}), "
                        "sehingga tidak dapat dibandingkan.",
                observed=stage.throughput.raw,
                expected=asset.total_capacity.raw,
                question=f"Tahap '{stage.stage_name}' diukur dalam {stage.throughput.unit} sedangkan "
                         f"aset '{asset.asset_name}' dalam {asset.total_capacity.unit}. "
                         "Berapa faktor konversi antara keduanya, atau satuan mana yang harus dipakai?",
            ))
            continue
        if stage.throughput_per_hour <= asset_per_hour + 1e-6:
            continue
        report.add(ValidationIssue(
            code="THROUGHPUT_EXCEEDS_CAPACITY",
            severity=Severity.BLOCKING,
            sheet_key="stages",
            excel_row=stage.excel_row,
            column="throughput",
            entity_id=stage.stage_id,
            message=f"Throughput tahap '{stage.stage_id}' setara {stage.throughput_per_hour:g} "
                    f"{stage.throughput.unit}/jam, melampaui kapasitas aset '{asset.asset_id}' "
                    f"yang setara {asset_per_hour:g} {asset.total_capacity.unit}/jam.",
            observed=f"{stage.throughput_per_hour:g} {stage.throughput.unit}/jam",
            expected=f"maksimum {asset_per_hour:g} {asset.total_capacity.unit}/jam",
            question=f"Tahap '{stage.stage_name}' menargetkan {stage.throughput.raw} padahal aset "
                     f"'{asset.asset_name}' hanya sanggup {asset.total_capacity.raw}. "
                     "Angka mana yang benar, atau apakah ada unit aset tambahan yang belum didaftarkan?",
        ))


def _check_asset_function(workbook: FactoryWorkbook, report: ValidationReport) -> None:
    for stage in workbook.stages:
        asset = workbook.asset_by_id(stage.asset_id)
        if asset is None:
            continue
        stage_groups = _function_groups(f"{stage.stage_name} {stage.operator_task}")
        asset_groups = _function_groups(asset.asset_name)
        if not stage_groups or not asset_groups or stage_groups & asset_groups:
            continue
        stage_label = "/".join(sorted(stage_groups))
        asset_label = "/".join(sorted(asset_groups))
        report.add(ValidationIssue(
            code="ASSET_FUNCTION_MISMATCH",
            severity=Severity.WARNING,
            sheet_key="assets",
            excel_row=asset.excel_row,
            column="asset_name",
            entity_id=asset.asset_id,
            message=f"Aset '{asset.asset_id}' bernama '{asset.asset_name}' (fungsi {asset_label}) "
                    f"dipakai pada tahap '{stage.stage_name}' (fungsi {stage_label}).",
            observed=asset.asset_name,
            expected=f"peralatan untuk {stage_label}",
            question=f"Tahap '{stage.stage_name}' seharusnya memakai peralatan {stage_label}, "
                     f"tetapi aset '{asset.asset_id}' tercatat sebagai '{asset.asset_name}'. "
                     "Apakah nama aset ini tertukar dengan baris lain?",
        ))


def _check_material_chain(workbook: FactoryWorkbook, report: ValidationReport) -> None:
    predecessors: dict[str, list[StageRecord]] = defaultdict(list)
    for stage in workbook.stages:
        if stage.next_stage_id:
            predecessors[stage.next_stage_id].append(stage)

    for stage in workbook.stages:
        upstream = predecessors.get(stage.stage_id, [])
        if not upstream:
            continue
        available = {normalize(material) for source in upstream for material in source.material_output}
        for material in stage.material_input:
            if normalize(material) in available:
                continue
            report.add(ValidationIssue(
                code="MATERIAL_CHAIN_BREAK",
                severity=Severity.WARNING,
                sheet_key="stages",
                excel_row=stage.excel_row,
                column="material_input",
                entity_id=stage.stage_id,
                message=f"Tahap '{stage.stage_id}' membutuhkan material '{material}' yang tidak "
                        "dihasilkan tahap sebelumnya.",
                observed=material,
                expected=", ".join(sorted(
                    source_material
                    for source in upstream
                    for source_material in source.material_output
                )) or "(tidak ada keluaran)",
                question=f"Material '{material}' pada tahap '{stage.stage_name}' tidak muncul sebagai "
                         "keluaran tahap sebelumnya. Apakah material ini dipasok langsung dari gudang, "
                         "atau ada tahap yang belum didaftarkan?",
            ))


def _check_shared_assets(workbook: FactoryWorkbook, report: ValidationReport) -> None:
    for group in workbook.graph.parallel_groups:
        usage: dict[str, list[str]] = defaultdict(list)
        for stage_id in group["steps"]:
            stage = workbook.stage_by_id(stage_id)
            if stage and stage.asset_id:
                usage[stage.asset_id].append(stage_id)
        for asset_id, stage_ids in usage.items():
            if len(stage_ids) < 2:
                continue
            asset = workbook.asset_by_id(asset_id)
            units = asset.units_available if asset else None
            if units and units >= len(stage_ids):
                continue
            report.add(ValidationIssue(
                code="ASSET_CONTENTION",
                severity=Severity.WARNING,
                sheet_key="stages",
                excel_row=None,
                column="asset_id",
                entity_id=asset_id,
                message=f"Aset '{asset_id}' dipakai bersamaan oleh tahap paralel "
                        f"{', '.join(stage_ids)} pada grup {group['group_id']}, "
                        f"sementara unit tersedia hanya {units if units is not None else 'tidak diketahui'}.",
                observed=f"{len(stage_ids)} tahap paralel",
                expected=f"{len(stage_ids)} unit aset",
                question=f"Aset '{asset_id}' dibutuhkan serentak oleh {len(stage_ids)} tahap paralel. "
                         "Apakah jumlah unitnya lebih dari yang tercatat, atau tahap-tahap itu "
                         "sebenarnya bergantian?",
            ))


VALIDATORS = (
    _check_structure,
    _check_required_cells,
    _check_duplicate_ids,
    _check_foreign_keys,
    _check_graph,
    _check_coverage,
    _check_headcount,
    _check_double_booking,
    _check_automation_consistency,
    _check_capacity,
    _check_stage_capacity,
    _check_asset_function,
    _check_material_chain,
    _check_shared_assets,
)


def validate_workbook(workbook: FactoryWorkbook) -> ValidationReport:
    report = ValidationReport(source_name=workbook.source_name)
    for validator in VALIDATORS:
        validator(workbook, report)
    return report