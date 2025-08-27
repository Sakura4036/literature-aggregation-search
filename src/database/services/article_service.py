from typing import Optional, List
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from src.database.models import Article
from src.models.schemas import ArticleSchema


def _orm_to_schema(orm: Article) -> ArticleSchema:
    return ArticleSchema(
        primary_doi=orm.primary_doi,
        title=orm.title or "",
        abstract=orm.abstract,
        language=orm.language,
        publication_year=orm.publication_year,
        publication_date=orm.publication_date,
        updated_date=orm.updated_date,
        citation_count=orm.citation_count or 0,
        reference_count=orm.reference_count or 0,
        influential_citation_count=orm.influential_citation_count or 0,
        is_open_access=orm.is_open_access or False,
        open_access_url=orm.open_access_url,
    )


class ArticleService:

    @staticmethod
    async def get_by_id(article_id: int, session: AsyncSession) -> Optional[ArticleSchema]:
        """Return ArticleSchema or None. Session must be provided by caller (dependency-injected)."""
        q = select(Article).where(Article.id == article_id)
        res = await session.execute(q)
        orm = res.scalar_one_or_none()
        if orm is None:
            return None
        return _orm_to_schema(orm)

    @staticmethod
    async def get_by_doi(doi: str, session: AsyncSession) -> Optional[ArticleSchema]:
        q = select(Article).where(Article.primary_doi == doi)
        res = await session.execute(q)
        orm = res.scalar_one_or_none()
        if orm is None:
            return None
        return _orm_to_schema(orm)

    @staticmethod
    async def add_article(article: ArticleSchema, session: AsyncSession) -> ArticleSchema:
        """Create a single Article row from ArticleSchema. Validates input if a validate() method exists."""
        # optional, backward-compatible validation hook
        validator = getattr(article, "validate", None)
        if callable(validator):
            is_valid, errors = validator()
            if not is_valid:
                raise ValueError(f"Article validation failed: {errors}")

        orm = Article(
            primary_doi=article.primary_doi,
            title=article.title,
            abstract=article.abstract,
            language=article.language,
            publication_year=article.publication_year,
            publication_date=article.publication_date,
            citation_count=article.citation_count,
            reference_count=article.reference_count,
            influential_citation_count=article.influential_citation_count,
            is_open_access=article.is_open_access,
            open_access_url=article.open_access_url,
        )
        async with session.begin():
            session.add(orm)
            # flush happens on commit; ensure id is populated
            await session.flush()
        return _orm_to_schema(orm)

    @staticmethod
    async def update_article(article_id: int, article: ArticleSchema, session: AsyncSession) -> Optional[ArticleSchema]:
        q = select(Article).where(Article.id == article_id).with_for_update()
        res = await session.execute(q)
        orm = res.scalar_one_or_none()
        if orm is None:
            return None

        # update fields
        orm.title = article.title
        orm.abstract = article.abstract
        orm.language = article.language
        orm.publication_year = article.publication_year
        orm.publication_date = article.publication_date
        orm.citation_count = article.citation_count
        orm.reference_count = article.reference_count
        orm.influential_citation_count = article.influential_citation_count
        orm.is_open_access = article.is_open_access
        orm.open_access_url = article.open_access_url

        async with session.begin():
            session.add(orm)
            await session.flush()

        return _orm_to_schema(orm)

    @staticmethod
    async def delete_article(article_id: int, session: AsyncSession) -> bool:
        q = select(Article).where(Article.id == article_id)
        res = await session.execute(q)
        orm = res.scalar_one_or_none()
        if orm is None:
            return False
        async with session.begin():
            await session.delete(orm)
        return True
