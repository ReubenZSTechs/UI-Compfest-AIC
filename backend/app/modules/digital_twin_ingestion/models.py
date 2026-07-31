import uuid
from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base


class DigitalTwinSnapshot(Base):
    """
    Satu baris = satu snapshot lengkap digital twin sebuah pabrik.
    Disimpan sebagai JSONB agar struktur nested (assets, workers, job_desks,
    llm_compatibility_and_evaluations, factory_flow_rightnow) tidak perlu
    dipecah jadi banyak tabel bertautan — konsisten dengan bentuk output
    pipeline agent (factory_md_creator_agent, set_initial_state_agent, dst)
    yang memang menghasilkan satu blob JSON per factory.
    """
    __tablename__ = "digital_twin_snapshots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    factory_id = Column(String, nullable=False, unique=True, index=True)
    data = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )