# app/api/v1/router.py
from fastapi import APIRouter

from app.api.v1.endpoints import (
    digital_twin_ingestion,
    document_parser,
    factories,
    node_autofill,
    rl_optimization,
    simulation,
)

api_router = APIRouter()

# Kontrak kanonik: factory_id sebagai path param.
#   POST /factories
#   GET  /factories/{factory_id}/digital-twin
#   GET  /factories/{factory_id}/simulation-config
#   PUT  /factories/{factory_id}/simulation
api_router.include_router(factories.router, prefix="/factories", tags=["factories"])

api_router.include_router(
    digital_twin_ingestion.router, prefix="/digital-twin", tags=["digital-twin"]
)

# Alias tanpa tanda hubung: GET /digitaltwin/{factory_id}.
api_router.include_router(
    digital_twin_ingestion.router,
    prefix="/digitaltwin",
    tags=["digital-twin"],
    include_in_schema=False,
)

api_router.include_router(simulation.router, prefix="/simulation", tags=["simulation"])

api_router.include_router(
    rl_optimization.router, prefix="/rl-optimization", tags=["rl-optimization"]
)

api_router.include_router(
    document_parser.router, prefix="/documents", tags=["document-parser"]
)

api_router.include_router(node_autofill.router, prefix="/agents", tags=["agents"])