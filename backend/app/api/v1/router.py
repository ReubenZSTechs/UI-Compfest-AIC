# app/api/v1/router.py
from fastapi import APIRouter

from app.api.v1.endpoints import (
    document_parser,
    rl_optimization,
    digital_twin_ingestion,
    simulation,
)

api_router = APIRouter()

api_router.include_router(
    digital_twin_ingestion.router, prefix="/digital-twin", tags=["digital-twin"]
)

api_router.include_router(
    simulation.router,
    prefix="/simulation",
    tags=["simulation"],
)

# Tambahkan prefix="/documents" di sini
api_router.include_router(
    document_parser.router,
    prefix="/documents",
    tags=["document-parser"],
)