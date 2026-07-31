# app/api/v1/router.py
from fastapi import APIRouter

from app.api.v1.endpoints import (
    rl_optimization,
    digital_twin_ingestion,
    simulation
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