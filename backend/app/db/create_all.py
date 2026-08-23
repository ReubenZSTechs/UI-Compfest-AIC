# backend/app/db/create_all.py
"""
Membuat semua tabel langsung dari models.py (tanpa migration history).

Dipanggil otomatis lewat lifespan app/main.py setiap kali backend start, dan
bisa juga dijalankan manual:
    python -m app.db.create_all

Cocok untuk dev; untuk perubahan skema pada tabel yang sudah ada (alter column,
rename, dst.) pakai Alembic -- create_all() hanya menambahkan tabel yang belum
ada, tidak pernah mengubah tabel yang sudah eksis.
"""

import asyncio
import logging

from app.db.base import Base
from app.db.session import engine

# WAJIB import semua models.py di sini supaya ter-register ke Base.metadata.
# Urutan import tidak penting; SQLAlchemy menyelesaikan dependensi FK sendiri.
from app.modules.digital_twin_ingestion import models as _dt_models  # noqa: F401
from app.modules.documents import models as _doc_models  # noqa: F401
from app.modules.simulation import models as _sim_models  # noqa: F401

# from app.modules.rl_optimization import models as _rl_models  # noqa: F401

logger = logging.getLogger(__name__)


async def create_all() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Semua tabel berhasil dibuat (atau sudah ada sebelumnya).")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    asyncio.run(create_all())