from typing import Optional
from sqlalchemy import select

from src.database.connection import DbSession
from src.database.models import FundingAgency


class FundingService:
    """Static methods for funding agency lookup/creation."""

    @staticmethod
    async def get_or_create_by_name(name: str) -> Optional[int]:
        if not name:
            return None
        async with DbSession() as session:
            q = select(FundingAgency).where(FundingAgency.agency_name == name)
            res = await session.execute(q)
            orm = res.scalar_one_or_none()
            if orm:
                return orm.id
            orm = FundingAgency(agency_name=name)
            session.add(orm)
            await session.flush()
            await session.commit()
            return orm.id
