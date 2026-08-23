from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Naming convention eksplisit -- wajib kalau pakai Alembic autogenerate,
# supaya nama constraint (fk, ix, uq) konsisten & bisa di-diff dengan benar.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """Mixin created_at/updated_at standar.

    BUG FIX: sebelumnya diimpor oleh `app/modules/rl_optimization/models.py`
    (8 model class) tapi tidak pernah didefinisikan di sini -- ImportError
    laten yang tidak muncul saat `uvicorn` start normal (models.py modul ini
    tidak ter-import di jalur startup), tapi meledak begitu ada yang
    menjalankan Alembic autogenerate/migration atau `Base.metadata.create_all`
    untuk modul ini. Modul lain (digital_twin_ingestion, documents) mendeklarasi
    `created_at` manual per-model, jadi tidak kena masalah ini -- mixin ini
    sengaja dibuat generik supaya rl_optimization/models.py bisa dipakai tanpa
    ubahan lebih lanjut.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )