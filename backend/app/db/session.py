# app/db/session.py
"""
Async SQLAlchemy engine & session factory.

Dipakai lewat api/deps.py::get_db sebagai FastAPI dependency, dan
lewat lifespan di main.py untuk graceful shutdown (engine.dispose()).
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

# pool_size/max_overflow hanya valid untuk driver yang pakai QueuePool
# (mis. asyncpg untuk Postgres). Driver seperti aiosqlite (dipakai di
# tests/unit) memakai NullPool/StaticPool dan akan error kalau dikasih
# kwarg tersebut — jadi kita split kwargs berdasarkan dialect.
_engine_kwargs: dict = {
    "echo": settings.DB_ECHO,
    "pool_pre_ping": True,  # cek koneksi masih hidup sebelum dipakai
}

if settings.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs.update(
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=1800,  # daur ulang koneksi tiap 30 menit — hindari
                             # koneksi stale ditolak managed DB (RDS/Supabase dsb.)
    )

engine: AsyncEngine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

# expire_on_commit=False supaya object masih bisa diakses setelah commit
# tanpa trigger query ulang (berguna saat return object langsung di response)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Session per-request dengan commit/rollback otomatis:
    - commit kalau request selesai tanpa exception
    - rollback kalau ada exception (termasuk domain exception dari service layer)
    - session selalu ditutup di akhir (context manager `async with`)

    Repository layer (repository.py) sengaja hanya `flush()`, bukan
    `commit()` — commit final terjadi di sini, satu tempat, supaya satu
    request = satu transaksi atomik walau service layer memanggil
    beberapa fungsi repository sekaligus.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise