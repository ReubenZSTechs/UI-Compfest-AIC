from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.digital_twin_ingestion.models import DigitalTwinSnapshot


class DigitalTwinRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_latest(self) -> Optional[DigitalTwinSnapshot]:
        stmt = select(DigitalTwinSnapshot).order_by(
            DigitalTwinSnapshot.updated_at.desc()
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_factory_id(self, factory_id: str) -> Optional[DigitalTwinSnapshot]:
        stmt = select(DigitalTwinSnapshot).where(
            DigitalTwinSnapshot.factory_id == factory_id
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def upsert(self, factory_id: str, data: dict) -> DigitalTwinSnapshot:
        existing = await self.get_by_factory_id(factory_id)
        if existing:
            existing.data = data
            self.db.add(existing)
        else:
            existing = DigitalTwinSnapshot(factory_id=factory_id, data=data)
            self.db.add(existing)
        await self.db.commit()
        await self.db.refresh(existing)
        return existing