# app/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.agent_config import get_agent_settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import register_middlewares
from app.api.v1.router import api_router
from app.db.session import engine
from app.services.agent_registry_service import get_agent_registry

import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()

    agent_settings = get_agent_settings()
    agent_registry = get_agent_registry()
    app.state.agent_registry = agent_registry

    logger.info(f"Agent registry available roles: {agent_registry.list_roles()}")

    if settings.is_production or agent_settings.AGENT_EAGER_LOAD:
        agent_registry.preload()
        logger.info(f"All agent eagerly loaded")

    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        lifespan=lifespan,
    )

    register_middlewares(app)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    register_exception_handlers(app)

    return app


app = create_app()


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}


@app.get("/health/agents", tags=["health"])
async def agent_health_check():
    registry = app.state.agent_registry
    roles = registry.list_roles()
    loaded = [role for role in roles if registry.is_loaded(role)]

    return {
        "status": "ok",
        "discovered_roles": roles,
        "loaded_roles": loaded,
    }
