from dataclasses import dataclass, field
from enum import StrEnum


class GapSeverity(StrEnum):
    BLOCKING = "blocking"
    WARNING = "warning"


@dataclass
class FieldGap:
    path: str
    severity: GapSeverity
    message: str
    question: str


@dataclass
class CompletenessReport:
    is_complete: bool
    blocking_count: int
    warning_count: int
    gaps: list[FieldGap] = field(default_factory=list)

    def blocking_gaps(self) -> list[FieldGap]:
        result = []
        for gap in self.gaps:
            if gap.severity == GapSeverity.BLOCKING:
                result.append(gap)
        return result

    def as_prompt_payload(self) -> str:
        lines = []
        for gap in self.gaps:
            lines.append(f"- [{gap.severity}] {gap.path}: {gap.message}")
        return "\n".join(lines)


PLACEHOLDER_VALUES = {"", "-", "n/a", "na", "tbd", "unknown", "tidak diketahui", "null"}


class FactoryCompletenessChecker:
    def __init__(self, twin: dict):
        self.twin = twin
        self.gaps: list[FieldGap] = []

    def _is_blank(self, value) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip().lower() in PLACEHOLDER_VALUES
        if isinstance(value, (list, dict)):
            return len(value) == 0
        return False

    def _add(self, path: str, severity: GapSeverity, message: str, question: str) -> None:
        self.gaps.append(
            FieldGap(path=path, severity=severity, message=message, question=question)
        )

    def check_factory_info(self) -> None:
        info = self.twin.get("factory_info")

        if not info:
            self._add(
                path="factory_info",
                severity=GapSeverity.BLOCKING,
                message="Blok factory_info tidak ditemukan.",
                question="Bisa sebutkan nama pabrik, jenis proses (serial atau parallel), dan jumlah pekerja?",
            )
            return

        required_text = {
            "factory_name": "Siapa nama pabrik dan di kota mana lokasinya?",
            "layout_description": "Bisa jelaskan singkat tata letak lantai produksi dan alur perpindahan barangnya?",
        }

        for key, question in required_text.items():
            if self._is_blank(info.get(key)):
                self._add(
                    path=f"factory_info.{key}",
                    severity=GapSeverity.BLOCKING,
                    message=f"Field {key} kosong atau berisi placeholder.",
                    question=question,
                )

        process_type = info.get("process_type")
        if process_type not in ("serial", "parallel"):
            self._add(
                path="factory_info.process_type",
                severity=GapSeverity.BLOCKING,
                message="process_type harus bernilai serial atau parallel.",
                question="Apakah proses produksi berjalan serial (satu tahap setelah tahap lain) atau parallel (beberapa tahap bersamaan)?",
            )

        worker_count = info.get("declared_worker_count")
        if not isinstance(worker_count, int) or worker_count < 1:
            self._add(
                path="factory_info.declared_worker_count",
                severity=GapSeverity.BLOCKING,
                message="Jumlah pekerja tidak terbaca sebagai angka positif.",
                question="Berapa jumlah total pekerja di lantai produksi?",
            )

        sequence = info.get("workflow_sequence")
        if self._is_blank(sequence):
            self._add(
                path="factory_info.workflow_sequence",
                severity=GapSeverity.BLOCKING,
                message="Urutan tahapan produksi kosong.",
                question="Bisa sebutkan tahapan produksi dari bahan baku sampai barang jadi secara berurutan?",
            )

        if process_type == "parallel" and self._is_blank(info.get("parallel_groups")):
            self._add(
                path="factory_info.parallel_groups",
                severity=GapSeverity.WARNING,
                message="Proses ditandai parallel tetapi tidak ada kelompok tahapan paralel.",
                question="Tahapan mana saja yang benar-benar bisa berjalan bersamaan tanpa saling menunggu?",
            )

    def check_step_coverage(self) -> None:
        info = self.twin.get("factory_info") or {}
        sequence = info.get("workflow_sequence") or []
        assets = self.twin.get("assets") or []
        job_descriptions = self.twin.get("job_descriptions") or []

        asset_steps = set()
        for asset in assets:
            asset_steps.add(asset.get("workflow_step"))

        job_steps = set()
        for job in job_descriptions:
            job_steps.add(job.get("workflow_step"))

        for step in sequence:
            if step not in asset_steps:
                self._add(
                    path=f"assets[workflow_step={step}]",
                    severity=GapSeverity.BLOCKING,
                    message=f"Tahapan {step} tidak punya aset.",
                    question=f"Alat atau mesin apa yang dipakai pada tahapan {step}? Tulis 'manual' bila tanpa alat.",
                )

            if step not in job_steps:
                self._add(
                    path=f"job_descriptions[workflow_step={step}]",
                    severity=GapSeverity.BLOCKING,
                    message=f"Tahapan {step} tidak punya job desk.",
                    question=f"Apa deskripsi pekerjaan operator pada tahapan {step}?",
                )

        for step in asset_steps:
            if step not in sequence:
                self._add(
                    path=f"assets[workflow_step={step}]",
                    severity=GapSeverity.WARNING,
                    message=f"Aset merujuk tahapan {step} yang tidak ada di workflow_sequence.",
                    question=f"Apakah tahapan {step} memang bagian dari alur produksi?",
                )

    def check_assets(self) -> None:
        assets = self.twin.get("assets") or []

        for asset in assets:
            asset_id = asset.get("asset_id", "tanpa-id")
            name = asset.get("asset_name", asset_id)

            if self._is_blank(asset.get("asset_name")):
                self._add(
                    path=f"assets.{asset_id}.asset_name",
                    severity=GapSeverity.BLOCKING,
                    message="Nama aset kosong.",
                    question=f"Apa nama alat atau mesin untuk {asset_id}?",
                )

            units = asset.get("units_available")
            if units is None:
                self._add(
                    path=f"assets.{asset_id}.units_available",
                    severity=GapSeverity.WARNING,
                    message="Jumlah unit alat tidak tercantum.",
                    question=f"Ada berapa unit {name} yang tersedia?",
                )

            if asset.get("is_automated") is None:
                self._add(
                    path=f"assets.{asset_id}.is_automated",
                    severity=GapSeverity.BLOCKING,
                    message="Status otomatisasi tidak diketahui.",
                    question=f"Apakah {name} berjalan otomatis atau dioperasikan manual?",
                )

            env = asset.get("environmental_factors") or {}
            for key in ("noise_level_db", "vibration_hazard_level", "physical_strain_index"):
                if self._is_blank(env.get(key)):
                    self._add(
                        path=f"assets.{asset_id}.environmental_factors.{key}",
                        severity=GapSeverity.WARNING,
                        message=f"Faktor lingkungan {key} kosong.",
                        question=f"Seberapa bising, bergetar, dan berat secara fisik pekerjaan di {name}?",
                    )
                    break

    def check_job_descriptions(self) -> None:
        assets = self.twin.get("assets") or []
        job_descriptions = self.twin.get("job_descriptions") or []

        known_asset_ids = set()
        for asset in assets:
            known_asset_ids.add(asset.get("asset_id"))

        for job in job_descriptions:
            job_id = job.get("job_id", "tanpa-id")
            title = job.get("job_title", job_id)
            assigned_asset = job.get("assigned_asset_id")

            if assigned_asset not in known_asset_ids:
                self._add(
                    path=f"job_descriptions.{job_id}.assigned_asset_id",
                    severity=GapSeverity.BLOCKING,
                    message=f"assigned_asset_id '{assigned_asset}' tidak cocok dengan aset mana pun.",
                    question=f"Alat mana yang dipakai pada pekerjaan {title}?",
                )

            if self._is_blank(job.get("assigned_worker_names")):
                self._add(
                    path=f"job_descriptions.{job_id}.assigned_worker_names",
                    severity=GapSeverity.WARNING,
                    message="Belum ada pekerja yang ditugaskan.",
                    question=f"Siapa pekerja yang bertugas pada {title}?",
                )

            demands = job.get("demands") or {}
            for key in (
                "required_cognitive_focus",
                "physical_demand_level",
                "task_complexity",
                "error_severity",
            ):
                if self._is_blank(demands.get(key)):
                    self._add(
                        path=f"job_descriptions.{job_id}.demands.{key}",
                        severity=GapSeverity.WARNING,
                        message=f"Tuntutan kerja {key} kosong.",
                        question=f"Seberapa berat tuntutan fokus dan fisik pada pekerjaan {title}?",
                    )
                    break

    def check_worker_count_consistency(self) -> None:
        info = self.twin.get("factory_info") or {}
        declared = info.get("declared_worker_count")

        if not isinstance(declared, int):
            return

        assigned_names = set()
        for job in self.twin.get("job_descriptions") or []:
            for name in job.get("assigned_worker_names") or []:
                assigned_names.add(name.strip().lower())

        if not assigned_names:
            return

        if len(assigned_names) < declared:
            missing = declared - len(assigned_names)
            self._add(
                path="job_descriptions.assigned_worker_names",
                severity=GapSeverity.WARNING,
                message=(
                    f"Jumlah pekerja dideklarasikan {declared} "
                    f"tetapi hanya {len(assigned_names)} nama yang ditugaskan."
                ),
                question=f"Ada {missing} pekerja yang belum ditempatkan. Siapa saja mereka dan di tahapan mana?",
            )

    def run(self) -> CompletenessReport:
        self.gaps = []

        self.check_factory_info()
        self.check_step_coverage()
        self.check_assets()
        self.check_job_descriptions()
        self.check_worker_count_consistency()

        blocking = 0
        warning = 0
        for gap in self.gaps:
            if gap.severity == GapSeverity.BLOCKING:
                blocking += 1
            else:
                warning += 1

        return CompletenessReport(
            is_complete=(blocking == 0),
            blocking_count=blocking,
            warning_count=warning,
            gaps=self.gaps,
        )


def check_factory_completeness(twin: dict) -> CompletenessReport:
    return FactoryCompletenessChecker(twin).run()