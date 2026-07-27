# app/modules/digital_twin_ingestion/exceptions.py
"""
Exception hierarchy khusus domain Digital Twin Ingestion.

Konvensi:
- Semua exception domain turun dari `DigitalTwinIngestionError` supaya bisa
  ditangkap secara generik di service/api layer kalau perlu.
- Setiap exception membawa `http_status` supaya handler generik di
  `app/core/exceptions.py` (register_exception_handlers) bisa langsung
  menerjemahkan ke JSONResponse tanpa if/elif panjang per tipe.
- Pesan (`detail`) dibuat deskriptif & aman ditampilkan ke user (bukan
  stack trace / internal detail).
"""

from __future__ import annotations

from uuid import UUID


class DigitalTwinIngestionError(Exception):
    """Base exception untuk seluruh error domain digital_twin_ingestion."""

    http_status: int = 400

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


# 1. Upload & file validation

class UnsupportedFileTypeError(DigitalTwinIngestionError):
    http_status = 415

    def __init__(self, filename: str, content_type: str, allowed: list[str]):
        self.filename = filename
        self.content_type = content_type
        self.allowed = allowed
        super().__init__(
            f"File '{filename}' bertipe '{content_type}' tidak didukung. "
            f"Tipe yang diizinkan: {', '.join(allowed)}."
        )


class FileTooLargeError(DigitalTwinIngestionError):
    http_status = 413

    def __init__(self, filename: str, size_bytes: int, max_bytes: int):
        self.filename = filename
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
        super().__init__(
            f"File '{filename}' berukuran {size_bytes} bytes, melebihi batas maksimum "
            f"{max_bytes} bytes."
        )


class MissingRequiredTableError(DigitalTwinIngestionError):
    http_status = 422

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(
            "Upload tidak lengkap, tabel wajib berikut belum disertakan: "
            f"{', '.join(missing)}."
        )


class EmptyCVBatchError(DigitalTwinIngestionError):
    http_status = 422

    def __init__(self):
        super().__init__("Minimal satu file CV harus disertakan untuk memulai ingestion job.")


# 2. Job lifecycle

class IngestionJobNotFoundError(DigitalTwinIngestionError):
    http_status = 404

    def __init__(self, job_id: UUID | str):
        self.job_id = job_id
        super().__init__(f"Ingestion job '{job_id}' tidak ditemukan.")


class InvalidStatusTransitionError(DigitalTwinIngestionError):
    """Dilempar saat service mencoba memindahkan status di luar alur pipeline yang sah
    (upload -> parsing_tables -> parsing_cvs -> merging -> synthesizing ->
    ready_for_review -> committed), mis. commit langsung dari status 'queued'."""

    http_status = 409

    def __init__(self, job_id: UUID | str, current_status: str, attempted_status: str):
        self.job_id = job_id
        self.current_status = current_status
        self.attempted_status = attempted_status
        super().__init__(
            f"Job '{job_id}' berstatus '{current_status}', tidak bisa dipindahkan "
            f"ke status '{attempted_status}'."
        )


class IngestionJobFailedError(DigitalTwinIngestionError):
    """Job sudah berstatus 'failed' — operasi lanjutan (patch/commit) tidak diizinkan."""

    http_status = 409

    def __init__(self, job_id: UUID | str, error_message: str | None):
        self.job_id = job_id
        self.error_message = error_message
        reason = f": {error_message}" if error_message else "."
        super().__init__(f"Job '{job_id}' gagal diproses{reason}")


class IngestionJobNotCancellableError(DigitalTwinIngestionError):
    http_status = 409

    def __init__(self, job_id: UUID | str, current_status: str):
        self.job_id = job_id
        self.current_status = current_status
        super().__init__(
            f"Job '{job_id}' berstatus '{current_status}' dan tidak bisa dibatalkan "
            "(job sudah selesai atau sudah di-cancel sebelumnya)."
        )


# 3. Draft & review

class DraftNotFoundError(DigitalTwinIngestionError):
    http_status = 404

    def __init__(self, job_id: UUID | str):
        self.job_id = job_id
        super().__init__(
            f"Draft untuk job '{job_id}' belum tersedia (tahap 'synthesizing' "
            "kemungkinan belum selesai)."
        )


class DraftNotReadyForReviewError(DigitalTwinIngestionError):
    http_status = 409

    def __init__(self, job_id: UUID | str, current_status: str):
        self.job_id = job_id
        self.current_status = current_status
        super().__init__(
            f"Draft job '{job_id}' belum siap direview, status saat ini: '{current_status}'."
        )


class ReviewRequiredError(DigitalTwinIngestionError):
    """Commit ditolak karena masih ada unmatched_cvs atau ambiguous_matches
    yang belum diresolusi oleh manusia."""

    http_status = 409

    def __init__(self, job_id: UUID | str, unresolved_ambiguities: int, unmatched_cvs: int):
        self.job_id = job_id
        self.unresolved_ambiguities = unresolved_ambiguities
        self.unmatched_cvs = unmatched_cvs
        super().__init__(
            f"Draft job '{job_id}' masih memiliki {unresolved_ambiguities} ambiguitas CV "
            f"dan {unmatched_cvs} CV yang belum ter-assign. Selesaikan review sebelum commit."
        )


class DigitalTwinAlreadyCommittedError(DigitalTwinIngestionError):
    http_status = 409

    def __init__(self, job_id: UUID | str):
        self.job_id = job_id
        super().__init__(f"Job '{job_id}' sudah pernah di-commit sebelumnya dan bersifat immutable.")


# 4. Patch operations (human-in-the-loop koreksi)

class PatchTargetNotFoundError(DigitalTwinIngestionError):
    http_status = 404

    def __init__(self, target_type: str, target_id: str):
        self.target_type = target_type
        self.target_id = target_id
        super().__init__(f"{target_type} dengan id '{target_id}' tidak ditemukan pada draft.")


class InvalidFieldPathError(DigitalTwinIngestionError):
    http_status = 422

    def __init__(self, field_path: str, reason: str | None = None):
        self.field_path = field_path
        suffix = f" ({reason})" if reason else ""
        super().__init__(f"Field path '{field_path}' tidak valid{suffix}.")


class CVAlreadyAssignedError(DigitalTwinIngestionError):
    http_status = 409

    def __init__(self, cv_filename: str, existing_worker_id: str):
        self.cv_filename = cv_filename
        self.existing_worker_id = existing_worker_id
        super().__init__(
            f"CV '{cv_filename}' sudah ter-assign ke worker '{existing_worker_id}'. "
            "Gunakan reassign_cv untuk memindahkan, bukan set_field."
        )


class WorkerNotFoundInDraftError(DigitalTwinIngestionError):
    http_status = 404

    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        super().__init__(f"Worker '{worker_id}' tidak ditemukan pada draft saat ini.")


class EmptyPatchError(DigitalTwinIngestionError):
    http_status = 422

    def __init__(self):
        super().__init__("Patch request tidak berisi operasi apapun.")


# 5. LLM / external dependency failures (parsing_cvs, synthesizing)

class CVExtractionFailedError(DigitalTwinIngestionError):
    http_status = 502

    def __init__(self, cv_filename: str, reason: str):
        self.cv_filename = cv_filename
        self.reason = reason
        super().__init__(f"Ekstraksi LLM untuk CV '{cv_filename}' gagal: {reason}")


class CompatibilitySynthesisFailedError(DigitalTwinIngestionError):
    http_status = 502

    def __init__(self, job_id: UUID | str, reason: str):
        self.job_id = job_id
        self.reason = reason
        super().__init__(
            f"Sintesis compatibility matrix untuk job '{job_id}' gagal: {reason}"
        )