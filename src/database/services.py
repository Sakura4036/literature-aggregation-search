"""
Database service functions for CRUD operations.

This module provides a higher-level API for interacting with the database,
encapsulating the database logic and session management.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, delete
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .connection import get_db_session
from src.models import schemas, enums


class LiteratureService:
    """
    A service class for handling literature data operations.
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create_or_update_article(self, literature: schemas.LiteratureSchema) -> models.Article:
        """
        Create a new article or update an existing one based on identifiers.
        """
        # First, try to find an existing article by DOI or other unique identifiers
        existing_article = await self._find_article_by_identifiers(literature.identifiers)

        if existing_article:
            # Update existing article
            return await self._update_article(existing_article, literature)
        else:
            # Create a new article
            return await self._create_article(literature)

    async def _find_article_by_identifiers(self, identifiers: List[schemas.IdentifierSchema]) -> Optional[models.Article]:
        """Find an article by its identifiers."""
        for identifier in identifiers:
            if identifier.identifier_value:
                stmt = select(models.Article).join(models.ArticleIdentifier).where(
                    models.ArticleIdentifier.identifier_type == identifier.identifier_type,
                    models.ArticleIdentifier.identifier_value == identifier.identifier_value
                )
                result = await self.db.execute(stmt)
                article = result.scalars().first()
                if article:
                    return article
        return None

    async def _create_article(self, literature: schemas.LiteratureSchema) -> models.Article:
        """Create a new article and its related entities."""
        # Create Article
        article_data = literature.article.to_dict()
        new_article = models.Article(**article_data)
        self.db.add(new_article)
        await self.db.flush() # Flush to get the new_article.id

        # Create related entities
        await self._create_or_update_authors(new_article.id, literature.authors)
        await self._create_or_update_venue(new_article.id, literature.venue, literature.publication)
        await self._create_or_update_identifiers(new_article.id, literature.identifiers)
        await self._create_or_update_categories(new_article.id, literature.categories)
        await self._create_or_update_publication_types(new_article.id, literature.publication_types)

        return new_article

    async def _update_article(self, article: models.Article, literature: schemas.LiteratureSchema) -> models.Article:
        """Update an existing article with new information."""
        # Update article fields
        article_data = literature.article.to_dict()
        for key, value in article_data.items():
            if value is not None:
                setattr(article, key, value)

        # Update related entities
        await self._create_or_update_authors(article.id, literature.authors)
        await self._create_or_update_venue(article.id, literature.venue, literature.publication)
        await self._create_or_update_identifiers(article.id, literature.identifiers)
        await self._create_or_update_categories(article.id, literature.categories)
        await self._create_or_update_publication_types(article.id, literature.publication_types)

        return article

    async def _create_or_update_authors(self, article_id: int, authors: List[schemas.AuthorSchema]):
        """Create or update authors and their relationship to the article."""
        # This is a simplified implementation. A real-world scenario would involve
        # more complex logic for finding and updating authors.
        for author_schema in authors:
            # Check if author exists
            stmt = select(models.Author).where(models.Author.full_name == author_schema.full_name)
            result = await self.db.execute(stmt)
            author = result.scalars().first()
            if not author:
                author = models.Author(
                    full_name=author_schema.full_name,
                    last_name=author_schema.last_name,
                    fore_name=author_schema.fore_name,
                    initials=author_schema.initials,
                    orcid=author_schema.orcid,
                    semantic_scholar_id=author_schema.semantic_scholar_id,
                )
                self.db.add(author)
                await self.db.flush()

            # Create article-author association
            assoc = models.ArticleAuthor(
                article_id=article_id,
                author_id=author.id,
                author_order=author_schema.author_order,
                is_corresponding=author_schema.is_corresponding
            )
            self.db.add(assoc)

    async def _create_or_update_venue(self, article_id: int, venue_schema: schemas.VenueSchema, pub_schema: schemas.PublicationSchema):
        """Create or update the venue and publication info."""
        if not venue_schema.venue_name:
            return

        stmt = select(models.Venue).where(models.Venue.venue_name == venue_schema.venue_name)
        result = await self.db.execute(stmt)
        venue = result.scalars().first()
        if not venue:
            venue = models.Venue(**venue_schema.to_dict())
            self.db.add(venue)
            await self.db.flush()

        pub = models.ArticlePublication(
            article_id=article_id,
            venue_id=venue.id,
            **pub_schema.to_dict()
        )
        self.db.add(pub)

    async def _create_or_update_identifiers(self, article_id: int, identifiers: List[schemas.IdentifierSchema]):
        """Create or update article identifiers."""
        for identifier_schema in identifiers:
            stmt = select(models.ArticleIdentifier).where(
                models.ArticleIdentifier.article_id == article_id,
                models.ArticleIdentifier.identifier_type == identifier_schema.identifier_type
            )
            result = await self.db.execute(stmt)
            existing = result.scalars().first()
            if not existing:
                identifier = models.ArticleIdentifier(
                    article_id=article_id,
                    **identifier_schema.to_dict()
                )
                self.db.add(identifier)

    async def _create_or_update_categories(self, article_id: int, categories: List[schemas.CategorySchema]):
        """Create or update subject categories."""
        for category_schema in categories:
            stmt = select(models.SubjectCategory).where(
                models.SubjectCategory.category_name == category_schema.category_name,
                models.SubjectCategory.category_type == category_schema.category_type
            )
            result = await self.db.execute(stmt)
            category = result.scalars().first()
            if not category:
                category = models.SubjectCategory(
                    category_name=category_schema.category_name,
                    category_code=category_schema.category_code,
                    category_type=category_schema.category_type,
                )
                self.db.add(category)
                await self.db.flush()

            assoc = models.ArticleCategory(
                article_id=article_id,
                category_id=category.id,
                is_major_topic=category_schema.is_major_topic,
                confidence_score=category_schema.confidence_score,
            )
            self.db.add(assoc)

    async def _create_or_update_publication_types(self, article_id: int, pub_types: List[schemas.PublicationTypeSchema]):
        """Create or update publication types."""
        for pub_type_schema in pub_types:
            stmt = select(models.PublicationType).where(
                models.PublicationType.type_name == pub_type_schema.type_name
            )
            result = await self.db.execute(stmt)
            pub_type = result.scalars().first()
            if not pub_type:
                pub_type = models.PublicationType(**pub_type_schema.to_dict())
                self.db.add(pub_type)
                await self.db.flush()

            assoc = models.ArticlePublicationType(
                article_id=article_id,
                publication_type_id=pub_type.id
            )
            self.db.add(assoc)

    async def get_article_by_id(self, article_id: int) -> Optional[models.Article]:
        """Get an article by its primary key."""
        stmt = select(models.Article).where(models.Article.id == article_id).options(
            selectinload(models.Article.authors).joinedload(models.ArticleAuthor.author),
            selectinload(models.Article.identifiers),
            selectinload(models.Article.publications).joinedload(models.ArticlePublication.venue),
            selectinload(models.Article.categories).joinedload(models.ArticleCategory.category),
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_full_article_by_doi(self, doi: str) -> Optional[models.Article]:
        """
        Get a full article with all its relationships by its DOI.
        """
        stmt = select(models.Article).join(models.ArticleIdentifier).where(
            (models.ArticleIdentifier.identifier_type == enums.IdentifierType.DOI) &
            (models.ArticleIdentifier.identifier_value == doi)
        ).options(
            selectinload(models.Article.sources).joinedload(models.ArticleSource.source),
            selectinload(models.Article.identifiers),
            selectinload(models.Article.publications).joinedload(models.ArticlePublication.venue),
            selectinload(models.Article.authors).joinedload(models.ArticleAuthor.author).joinedload(models.Author.articles),
            selectinload(models.Article.categories).joinedload(models.ArticleCategory.category),
            selectinload(models.Article.publication_types_assoc).joinedload(models.ArticlePublicationType.publication_type),
            selectinload(models.Article.funding).joinedload(models.ArticleFunding.funding_agency),
            selectinload(models.Article.versions)
        )

        result = await self.db.execute(stmt)
        return result.scalars().first()
