"""
Base repository classes for UUID-based models.

This module provides base repository patterns that work with UUID primary keys
and demonstrate the new database architecture.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, TypeVar, Generic, Type
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from .mixins import UUIDMixin

T = TypeVar('T', bound=UUIDMixin)


class BaseRepository(Generic[T], ABC):
    """Base repository class for UUID-based models."""
    
    def __init__(self, session: AsyncSession, model_class: Type[T]):
        self.session = session
        self.model_class = model_class
    
    async def create(self, **kwargs) -> T:
        """Create a new record with UUID primary key."""
        instance = self.model_class(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance
    
    async def get_by_id(self, id: UUID) -> Optional[T]:
        """Get record by UUID."""
        result = await self.session.execute(
            select(self.model_class).where(self.model_class.id == id)
        )
        return result.scalar_one_or_none()
    
    async def update(self, id: UUID, **kwargs) -> Optional[T]:
        """Update record by UUID."""
        await self.session.execute(
            update(self.model_class)
            .where(self.model_class.id == id)
            .values(**kwargs)
        )
        return await self.get_by_id(id)
    
    async def delete(self, id: UUID) -> bool:
        """Delete record by UUID."""
        result = await self.session.execute(
            delete(self.model_class).where(self.model_class.id == id)
        )
        return result.rowcount > 0
    
    async def list_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """List records with pagination."""
        result = await self.session.execute(
            select(self.model_class)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())


class ArticleRepository(BaseRepository):
    """Repository for Article model with UUID support."""
    
    async def find_by_doi(self, doi: str) -> Optional['Article']:
        """Find article by DOI."""
        from .models import Article
        result = await self.session.execute(
            select(Article).where(Article.primary_doi == doi)
        )
        return result.scalar_one_or_none()
    
    async def find_by_title(self, title: str) -> List['Article']:
        """Find articles by title (case-insensitive)."""
        from .models import Article
        result = await self.session.execute(
            select(Article).where(Article.title.ilike(f'%{title}%'))
        )
        return list(result.scalars().all())
    
    async def get_with_authors(self, id: UUID) -> Optional['Article']:
        """Get article with authors loaded."""
        from .models import Article
        result = await self.session.execute(
            select(Article)
            .options(selectinload(Article.authors))
            .where(Article.id == id)
        )
        return result.scalar_one_or_none()


class AuthorRepository(BaseRepository):
    """Repository for Author model with UUID support."""
    
    async def find_by_orcid(self, orcid: str) -> Optional['Author']:
        """Find author by ORCID."""
        from .models import Author
        result = await self.session.execute(
            select(Author).where(Author.orcid == orcid)
        )
        return result.scalar_one_or_none()
    
    async def find_by_name_fuzzy(self, name: str) -> List['Author']:
        """Find authors by fuzzy name matching."""
        from .models import Author
        result = await self.session.execute(
            select(Author).where(Author.full_name.ilike(f'%{name}%'))
        )
        return list(result.scalars().all())