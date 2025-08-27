from typing import Optional
from sqlalchemy import select

from src.database.connection import DbSession
from src.database.models import PublicationType
from src.models.schemas import PublicationTypeSchema


class PublicationTypeService:
    @staticmethod
    async def get_or_create(pt: PublicationTypeSchema) -> int:
        if not isinstance(pt, PublicationTypeSchema):
            raise TypeError("get_or_create expects PublicationTypeSchema")
        async with DbSession() as session:
            if pt.type_name:
                q = select(PublicationType).where(PublicationType.type_name == pt.type_name)
                res = await session.execute(q)
                orm = res.scalar_one_or_none()
                if orm:
                    return orm.id
            orm = PublicationType(type_name=pt.type_name, type_code=pt.type_code, source_type=pt.source_type)
            session.add(orm)
            await session.flush()
            await session.commit()
            return orm.id
