from typing import Optional
from sqlalchemy import select

from src.database.connection import DbSession
from src.database.models import ArticleIdentifier
from src.models.schemas import IdentifierSchema
from src.models.enums import IdentifierType


class IdentifierService:
    """Static methods to manage ArticleIdentifier rows."""

    @staticmethod
    async def get_by_type_and_value(id_type: IdentifierType, value: str) -> Optional[IdentifierSchema]:
        async with DbSession() as session:
            q = select(ArticleIdentifier).where(ArticleIdentifier.identifier_type == id_type, ArticleIdentifier.identifier_value == value)
            res = await session.execute(q)
            orm = res.scalar_one_or_none()
            if orm is None:
                return None
            return IdentifierSchema(identifier_type=orm.identifier_type, identifier_value=orm.identifier_value, is_primary=orm.is_primary)

    @staticmethod
    async def create(article_id: int, ident: IdentifierSchema) -> int:
        if not isinstance(ident, IdentifierSchema):
            raise TypeError("create expects IdentifierSchema")
        async with DbSession() as session:
            orm = ArticleIdentifier(article_id=article_id, identifier_type=ident.identifier_type, identifier_value=ident.identifier_value, is_primary=ident.is_primary)
            session.add(orm)
            await session.flush()
            await session.commit()
            return orm.id
