from typing import Optional
from sqlalchemy import select

from src.database.connection import DbSession
from src.database.models import Author
from src.models.schemas import AuthorSchema


class AuthorService:
    """Static methods for author lookup/creation.

    Provides get_by_id, create, and get_or_create_by_name_or_orcid.
    """

    @staticmethod
    async def get_by_id(author_id: int) -> Optional[AuthorSchema]:
        async with DbSession() as session:
            q = select(Author).where(Author.id == author_id)
            res = await session.execute(q)
            orm = res.scalar_one_or_none()
            if orm is None:
                return None
            return AuthorSchema(full_name=orm.full_name, last_name=orm.last_name, fore_name=orm.fore_name, orcid=orm.orcid)

    @staticmethod
    async def create(author: AuthorSchema) -> int:
        if not isinstance(author, AuthorSchema):
            raise TypeError("create expects AuthorSchema")
        async with DbSession() as session:
            orm = Author(full_name=author.full_name, last_name=author.last_name, fore_name=author.fore_name, orcid=author.orcid)
            session.add(orm)
            await session.flush()
            await session.commit()
            return orm.id

    @staticmethod
    async def get_or_create_by_name_or_orcid(author: AuthorSchema) -> int:
        """Return existing author.id by ORCID or full_name, or create a new Author and return id."""
        if not isinstance(author, AuthorSchema):
            raise TypeError("get_or_create_by_name_or_orcid expects AuthorSchema")
        async with DbSession() as session:
            # Prefer ORCID lookup when available
            if author.orcid:
                q = select(Author).where(Author.orcid == author.orcid)
                res = await session.execute(q)
                orm = res.scalar_one_or_none()
                if orm:
                    return orm.id
            # Fallback to exact full_name match
            if author.full_name:
                q = select(Author).where(Author.full_name == author.full_name)
                res = await session.execute(q)
                orm = res.scalar_one_or_none()
                if orm:
                    return orm.id
            # Create new
            orm = Author(full_name=author.full_name, last_name=author.last_name, fore_name=author.fore_name, orcid=author.orcid)
            session.add(orm)
            await session.flush()
            await session.commit()
            return orm.id
