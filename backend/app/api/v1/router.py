# app/api/v1/router.py
from fastapi import APIRouter

from app.api.v1.endpoints import (
    rl_optimization,
    digital_twin_ingestion,
)

api_router = APIRouter()


api_router.include_router(
    digital_twin_ingestion.router,
    prefix="/digital-twin",
    tags=["digital_twin_ingestion"],
)

api_router.include_router(
    rl_optimization.router,
    prefix="/rl",
    tags=["rl_optimization"],
)