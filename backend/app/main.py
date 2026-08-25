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
from app.db.create_all import create_all
from app.services.agent_registry_service import get_agent_registry

# [BARU] Import fungsi mark_stale_jobs
from app.worker.tasks import mark_stale_jobs

import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()

    # [BARU] Membungkus inisialisasi DB dan sweeping job dengan try-except
    try:
        logger.info("Memastikan skema database sudah siap...")
        await create_all()
        logger.info("Skema database siap.")
        
        # [BARU] Menjalankan startup sweep
        # Job Tahap 5 berjalan in-process; apa pun yang masih `queued`/`running` di DB
        # saat startup berarti prosesnya mati di tengah jalan dan tidak akan pernah
        # selesai. Tandai sebagai gagal supaya UI tidak menunggu selamanya.
        stale_jobs = await mark_stale_jobs()
        if stale_jobs:
            logger.warning(f"{stale_jobs} job matriks kompatibilitas menggantung ditandai gagal.")
            
    except Exception as e:
        logger.error(f"Terjadi kesalahan kritis saat inisialisasi database atau startup sweep: {e}")
        # Jika Anda ingin aplikasi gagal menyala (fail-fast) saat DB error, uncomment baris di bawah:
        # raise e

    agent_settings = get_agent_settings()
    agent_registry = get_agent_registry()
    app.state.agent_registry = agent_registry
    agent_registry.assert_enum_roles_registered()
    
    logger.info(f"Agent registry available roles: {agent_registry.list_roles()}")

    if settings.is_production or agent_settings.AGENT_EAGER_LOAD:
        agent_registry.preload()
        logger.info("All agents eagerly loaded")

    yield
    
    # Menutup koneksi database dengan aman saat shutdown
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