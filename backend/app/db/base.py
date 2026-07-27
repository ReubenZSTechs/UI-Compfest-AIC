# app/db/base.py
"""
Base class SQLAlchemy declarative — semua model di modules/*/models.py
harus inherit dari `Base` ini supaya ter-registrasi ke metadata yang sama
(dipakai Alembic untuk autogenerate migration).
"""

from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Konvensi nama constraint/index — wajib supaya Alembic autogenerate
# menghasilkan nama yang deterministik & bisa di-downgrade dengan aman
# (tanpa ini, nama constraint jadi acak/None dan migration jadi rapuh).
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base declarative untuk seluruh model ORM di project ini."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class CreatedAtMixin:
    """Untuk record append-only/immutable (mis. log, snapshot, commit record)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TimestampMixin(CreatedAtMixin):
    """
    Mixin untuk model yang butuh created_at/updated_at otomatis.
    Pakai dengan: class Worker(Base, TimestampMixin): ...
    """

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
