"""
Database service functions for CRUD operations.

This module provides a higher-level API for interacting with the database,
encapsulating the database logic and session management.
"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models import schemas, enums
from .models import *
from src.database.connection import db_session


class LiteratureService:
    """
    A service class for handling literature data operations.
    """

    @staticmethod
    async def create_or_update_article(literature: schemas.LiteratureSchema) -> Article:
        """
        Create a new article or update an existing one based on identifiers.
        """
        # First, try to find an existing article by DOI or other unique identifiers
        existing_article = await LiteratureService._find_article_by_identifiers(literature.identifiers)

        if existing_article:
            # Update existing article
            return await LiteratureService._update_article(existing_article, literature)
        else:
            # Create a new article
            return await LiteratureService._create_article(literature)

    @staticmethod
    async def _find_article_by_identifiers(identifiers: List[schemas.IdentifierSchema]) -> Optional[Article]:
        """Find an article by its identifiers."""
        for identifier in identifiers:
            if identifier.identifier_value:
                stmt = select(Article).join(ArticleIdentifier).where(
                    ArticleIdentifier.identifier_type == identifier.identifier_type,
                    ArticleIdentifier.identifier_value == identifier.identifier_value
                )
                result = await db_session.execute(stmt)
                article = result.scalars().first()
                if article:
                    return article
        return None

    async def _create_article(literature: schemas.LiteratureSchema) -> Article:
        """Create a new article and its related entities."""
        # Create Article
        article_data = literature.article.to_dict()
        new_article = Article(**article_data)
        db_session.add(new_article)
        await db_session.flush() # Flush to get the new_article.id

        # Create related entities
        await LiteratureService._create_or_update_authors(new_article.id, literature.authors)
        await LiteratureService._create_or_update_venue(new_article.id, literature.venue, literature.publication)
        await LiteratureService._create_or_update_identifiers(new_article.id, literature.identifiers)
        await LiteratureService._create_or_update_categories(new_article.id, literature.categories)
        await LiteratureService._create_or_update_publication_types(new_article.id, literature.publication_types)

        return new_article

    async def _update_article(article: Article, literature: schemas.LiteratureSchema) -> Article:
        """Update an existing article with new information."""
        # Update article fields
        article_data = literature.article.to_dict()
        for key, value in article_data.items():
            if value is not None:
                setattr(article, key, value)

        # Update related entities
        await LiteratureService._create_or_update_authors(article.id, literature.authors)
        await LiteratureService._create_or_update_venue(article.id, literature.venue, literature.publication)
        await LiteratureService._create_or_update_identifiers(article.id, literature.identifiers)
        await LiteratureService._create_or_update_categories(article.id, literature.categories)
        await LiteratureService._create_or_update_publication_types(article.id, literature.publication_types)

        return article

    async def _create_or_update_authors(article_id: int, authors: List[schemas.AuthorSchema]):
        """Create or update authors and their relationship to the article."""
        # This is a simplified implementation. A real-world scenario would involve
        # more complex logic for finding and updating authors.
        for author_schema in authors:
            # Check if author exists
            stmt = select(Author).where(Author.full_name == author_schema.full_name)
            result = await db_session.execute(stmt)
            author = result.scalars().first()
            if not author:
                author = Author(
                    full_name=author_schema.full_name,
                    last_name=author_schema.last_name,
                    fore_name=author_schema.fore_name,
                    initials=author_schema.initials,
                    orcid=author_schema.orcid,
                    semantic_scholar_id=author_schema.semantic_scholar_id,
                )
                db_session.add(author)
                await db_session.flush()

            # Create article-author association
            assoc = ArticleAuthor(
                article_id=article_id,
                author_id=author.id,
                author_order=author_schema.author_order,
                is_corresponding=author_schema.is_corresponding
            )
            db_session.add(assoc)

    async def _create_or_update_venue(article_id: int, venue_schema: schemas.VenueSchema, pub_schema: schemas.PublicationSchema):
        """Create or update the venue and publication info."""
        if not venue_schema.venue_name:
            return

        stmt = select(Venue).where(Venue.venue_name == venue_schema.venue_name)
        result = await db_session.execute(stmt)
        venue = result.scalars().first()
        if not venue:
            venue = Venue(**venue_schema.to_dict())
            db_session.add(venue)
            await db_session.flush()

        pub = ArticlePublication(
            article_id=article_id,
            venue_id=venue.id,
            **pub_schema.to_dict()
        )
        db_session.add(pub)

    async def _create_or_update_identifiers(article_id: int, identifiers: List[schemas.IdentifierSchema]):
        """Create or update article identifiers."""
        for identifier_schema in identifiers:
            stmt = select(ArticleIdentifier).where(
                ArticleIdentifier.article_id == article_id,
                ArticleIdentifier.identifier_type == identifier_schema.identifier_type
            )
            result = await db_session.execute(stmt)
            existing = result.scalars().first()
            if not existing:
                identifier = ArticleIdentifier(
                    article_id=article_id,
                    **identifier_schema.to_dict()
                )
                db_session.add(identifier)

    async def _create_or_update_categories(article_id: int, categories: List[schemas.CategorySchema]):
        """Create or update subject categories."""
        for category_schema in categories:
            stmt = select(SubjectCategory).where(
                SubjectCategory.category_name == category_schema.category_name,
                SubjectCategory.category_type == category_schema.category_type
            )
            result = await db_session.execute(stmt)
            category = result.scalars().first()
            if not category:
                category = SubjectCategory(
                    category_name=category_schema.category_name,
                    category_code=category_schema.category_code,
                    category_type=category_schema.category_type,
                )
                db_session.add(category)
                await db_session.flush()

            assoc = ArticleCategory(
                article_id=article_id,
                category_id=category.id,
                is_major_topic=category_schema.is_major_topic,
                confidence_score=category_schema.confidence_score,
            )
            db_session.add(assoc)

    async def _create_or_update_publication_types(article_id: int, pub_types: List[schemas.PublicationTypeSchema]):
        """Create or update publication types."""
        for pub_type_schema in pub_types:
            stmt = select(PublicationType).where(
                PublicationType.type_name == pub_type_schema.type_name
            )
            result = await db_session.execute(stmt)
            pub_type = result.scalars().first()
            if not pub_type:
                pub_type = PublicationType(**pub_type_schema.to_dict())
                db_session.add(pub_type)
                await db_session.flush()

            assoc = ArticlePublicationType(
                article_id=article_id,
                publication_type_id=pub_type.id
            )
            db_session.add(assoc)

    async def get_article_by_id(article_id: int) -> Optional[Article]:
        """Get an article by its primary key."""
        stmt = select(Article).where(Article.id == article_id).options(
            selectinload(Article.authors).joinedload(ArticleAuthor.author),
            selectinload(Article.identifiers),
            selectinload(Article.publications).joinedload(ArticlePublication.venue),
            selectinload(Article.categories).joinedload(ArticleCategory.category),
        )
        result = await db_session.execute(stmt)
        return result.scalars().first()

    async def get_full_article_by_doi(doi: str) -> Optional[Article]:
        """
        Get a full article with all its relationships by its DOI.
        """
        stmt = select(Article).join(ArticleIdentifier).where(
            (ArticleIdentifier.identifier_type == enums.IdentifierType.DOI) &
            (ArticleIdentifier.identifier_value == doi)
        ).options(
            selectinload(Article.sources).joinedload(ArticleSource.source),
            selectinload(Article.identifiers),
            selectinload(Article.publications).joinedload(ArticlePublication.venue),
            selectinload(Article.authors).joinedload(ArticleAuthor.author).joinedload(Author.articles),
            selectinload(Article.categories).joinedload(ArticleCategory.category),
            selectinload(Article.publication_types_assoc).joinedload(ArticlePublicationType.publication_type),
            selectinload(Article.funding).joinedload(ArticleFunding.funding_agency),
            selectinload(Article.versions)
        )

        result = await db_session.execute(stmt)
        return result.scalars().first()
