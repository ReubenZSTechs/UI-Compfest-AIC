"""
backend/app/modules/documents/exceptions.py

Exception khusus modul documents (document-parser pipeline 5 tahap & alur kombinasi 1-5).
"""

from __future__ import annotations

from typing import Any


class DocumentParserPipelineError(Exception):
    """Error yang membawa info tahap mana proses document-parser gagal,
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