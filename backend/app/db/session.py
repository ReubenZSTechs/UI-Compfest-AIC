from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings  # asumsi: settings.DATABASE_URL sudah ada di sini

# echo=False di production; nyalakan lewat env kalau butuh debug SQL.
engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # penting: biar object masih bisa dibaca setelah commit tanpa re-query
    autoflush=False,
)


async def get_db():
    """Dependency FastAPI: satu session per-request, auto-close."""
    async with AsyncSessionLocal() as session:
        yield session

get_session = get_db