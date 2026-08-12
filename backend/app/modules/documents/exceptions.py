"""
backend/app/modules/documents/exceptions.py

Exception khusus modul documents (document-parser pipeline 5 tahap & alur kombinasi 1-5).
"""

from __future__ import annotations

from typing import Any


class DocumentParserPipelineError(Exception):
    """Base error yang membawa info tahap mana proses document-parser gagal,
    supaya endpoint (step-1 s/d step-5 & endpoint kombinasi 1-5) dapat memetakannya
    secara konsisten ke HTTP 422 response body untuk frontend.

    Nilai stage yang umum digunakan:
    - "upload"        : Format berkas tidak valid / ekstensi bukan .zip / file rusak 
                        (Tahap 1, 4, & Kombinasi 1-5)
    - "extract"       : Gagal membaca tabel PDF atau ekstraksi arsip ZIP CV 
                        (Tahap 1, 4, & Kombinasi 1-5)
    - "llm_parse"     : Gagal saat pemanggilan LLM Agent A (Struktur Pabrik) atau Agent B (Profil Pekerja) 
                        (Tahap 2, 4, & Kombinasi 1-5)
    - "validate"      : Kegagalan validasi struktur data / blocking gaps 
                        (Tahap 3)
    - "compatibility" : Gagal saat pembuatan/evaluasi matriks kompatibilitas 
                        (Tahap 5 & Kombinasi 1-5)
    """

    def __init__(
        self,
        stage: str,
        message: str,
        *,
        details: list[Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message
        self.details = details or []

    def to_dict(self) -> dict[str, Any]:
        """Konversi error ke format dictionary standar untuk response HTTP 422."""
        return {
            "stage": self.stage,
            "message": self.message,
            "details": self.details,
        }

    def __repr__(self) -> str:
        return f"DocumentParserPipelineError(stage='{self.stage}', message='{self.message}')"


# --- Sub-exceptions Khusus per Tahap Pipeline (Opsional / Helper) ---

class DocumentUploadError(DocumentParserPipelineError):
    """Error khusus pada Tahap 1/4 Upload & Validasi Berkas awal."""
    def __init__(self, message: str, details: list[Any] | None = None) -> None:
        super().__init__(stage="upload", message=message, details=details)


class DocumentExtractionError(DocumentParserPipelineError):
    """Error khusus pada Tahap Ekstraksi Berkas/Tabel/Unzip."""
    def __init__(self, message: str, details: list[Any] | None = None) -> None:
        super().__init__(stage="extract", message=message, details=details)


class LLMParseError(DocumentParserPipelineError):
    """Error khusus pada Tahap Pemrosesan LLM Agent A / Agent B."""
    def __init__(self, message: str, details: list[Any] | None = None) -> None:
        super().__init__(stage="llm_parse", message=message, details=details)


class DocumentValidationError(DocumentParserPipelineError):
    """Error khusus pada Tahap Validasi & Gap Detection."""
    def __init__(self, message: str, details: list[Any] | None = None) -> None:
        super().__init__(stage="validate", message=message, details=details)


class CompatibilityError(DocumentParserPipelineError):
    """Error khusus pada Tahap 5 Kompatibilitas Matriks."""
    def __init__(self, message: str, details: list[Any] | None = None) -> None:
        super().__init__(stage="compatibility", message=message, details=details)