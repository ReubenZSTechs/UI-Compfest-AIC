# app/api/v1/router.py
from fastapi import APIRouter

from app.api.v1.endpoints import (
    document_parser,
    rl_optimization,
    digital_twin_ingestion,
    simulation,
    factories,
)

api_router = APIRouter()

# Kontrak kanonik baru: factory_id sebagai path param, bukan query opsional.
# GET /factories/{factory_id}/digital-twin
# GET /factories/{factory_id}/simulation-config
api_router.include_router(
    factories.router, prefix="/factories", tags=["factories"]
)

api_router.include_router(
    digital_twin_ingestion.router, prefix="/digital-twin", tags=["digital-twin"]
)

api_router.include_router(
    simulation.router,
    prefix="/simulation",
    tags=["simulation"],
)

# FIX: router rl_optimization sebelumnya diimpor tapi tidak pernah di-include,
# jadi GET /rl-optimization/digital-twin (Fase Inisialisasi untuk
# features/simulation_optimisation) sebenarnya tidak pernah reachable.
api_router.include_router(
    rl_optimization.router,
    prefix="/rl-optimization",
    tags=["rl-optimization"],
)

# Tambahkan prefix="/documents" di sini
api_router.include_router(
    document_parser.router,
    prefix="/documents",
    tags=["document-parser"],
)