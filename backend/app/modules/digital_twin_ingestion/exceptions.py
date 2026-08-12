"""
backend/app/modules/digital_twin_ingestion/exceptions.py
"""

from app.modules.documents.exceptions import (
    DocumentParserPipelineError,
    DocumentUploadError,
    DocumentExtractionError,
    LLMParseError,
    DocumentValidationError,
    CompatibilityError,
)

__all__ = [
    "DocumentParserPipelineError",
    "DocumentUploadError",
    "DocumentExtractionError",
    "LLMParseError",
    "DocumentValidationError",
    "CompatibilityError",
]