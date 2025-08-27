from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import PublicationType
from src.models.schemas import PublicationTypeSchema


class PublicationTypeService:
    @staticmethod
    async def get_by_id(pt_id: int, session: AsyncSession) -> Optional[PublicationTypeSchema]:
        q = select(PublicationType).where(PublicationType.id == pt_id)
        res = await session.execute(q)
        orm = res.scalar_one_or_none()
        if orm is None:
            return None
        return PublicationTypeSchema(type_name=orm.type_name, type_code=orm.type_code, source_type=orm.source_type)

    @staticmethod
    async def get_or_create(pt: PublicationTypeSchema, session: AsyncSession) -> int:
        if not isinstance(pt, PublicationTypeSchema):
            raise TypeError("get_or_create expects PublicationTypeSchema")
        if pt.type_name:
            q = select(PublicationType).where(PublicationType.type_name == pt.type_name)
            res = await session.execute(q)
            orm = res.scalar_one_or_none()
            if orm:
                return orm.id
        orm = PublicationType(type_name=pt.type_name, type_code=pt.type_code, source_type=pt.source_type)
        async with session.begin():
            session.add(orm)
            await session.flush()
        return orm.id
