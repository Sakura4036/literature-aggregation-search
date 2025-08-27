from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import DbSession
from src.database.models import Article, ArticleIdentifier, ArticleAuthor, ArticlePublication, ArticleSource
from src.models.schemas import LiteratureSchema, ArticleSchema, AuthorSchema, IdentifierSchema, PublicationSchema, VenueSchema, PublicationTypeSchema, CategorySchema
from src.models.enums import IdentifierType

from .author_service import AuthorService
from .venue_service import VenueService
from .funding_service import FundingService
from .subject_category_service import SubjectCategoryService
from .publication_type_service import PublicationTypeService


class ArticleService:
    """Service helpers for articles. All methods are static as requested.

    Contract:
    - insert/update methods accept a LiteratureSchema instance
    - query returns a LiteratureSchema instance
    """

    @staticmethod
    async def get_by_id(article_id: int) -> Optional[LiteratureSchema]:
        async with DbSession() as session:  # type: AsyncSession
            q = select(Article).where(Article.id == article_id)
            res = await session.execute(q)
            orm = res.scalar_one_or_none()
            if orm is None:
                return None
            return ArticleService._orm_to_schema(orm)

    @staticmethod
    async def get_by_doi(doi: str) -> Optional[LiteratureSchema]:
        async with DbSession() as session:
            q = select(Article).where(Article.primary_doi == doi)
            res = await session.execute(q)
            orm = res.scalar_one_or_none()
            if orm is None:
                return None
            return ArticleService._orm_to_schema(orm)

    @staticmethod
    async def insert(lit: LiteratureSchema) -> LiteratureSchema:
        if not isinstance(lit, LiteratureSchema):
            raise TypeError("insert expects a LiteratureSchema instance")
        async with DbSession() as session:
            article = Article(
                primary_doi=lit.article.primary_doi,
                title=lit.article.title,
                abstract=lit.article.abstract,
                language=lit.article.language,
                publication_year=lit.article.publication_year,
                publication_date=lit.article.publication_date,
                citation_count=lit.article.citation_count,
                reference_count=lit.article.reference_count,
                influential_citation_count=lit.article.influential_citation_count,
                is_open_access=lit.article.is_open_access,
                open_access_url=lit.article.open_access_url,
            )
            session.add(article)
            await session.flush()

            # identifiers
            for ident in lit.identifiers:
                ai = ArticleIdentifier(
                    article_id=article.id,
                    identifier_type=ident.identifier_type,
                    identifier_value=ident.identifier_value,
                    is_primary=ident.is_primary,
                )
                session.add(ai)

            # authors: ensure author records exist and create ArticleAuthor relations
            for idx, a in enumerate(lit.authors or []):
                # ensure existence and get id
                try:
                    author_id = await AuthorService.get_or_create_by_name_or_orcid(a)
                except Exception:
                    # fallback: create minimal author
                    author_id = await AuthorService.create(a)
                aa = ArticleAuthor(
                    article_id=article.id,
                    author_id=author_id,
                    author_order=(a.author_order if a.author_order is not None else (idx + 1)),
                    is_corresponding=a.is_corresponding,
                )
                session.add(aa)

            # publication and venue
            if getattr(lit, 'venue', None) and isinstance(lit.venue, VenueSchema) and lit.venue.venue_name:
                venue_id = await VenueService.get_or_create(lit.venue)
            else:
                venue_id = None
            if lit.publication and (lit.publication.volume or lit.publication.issue or lit.publication.article_number or venue_id):
                ap = ArticlePublication(
                    article_id=article.id,
                    venue_id=venue_id,
                    volume=lit.publication.volume,
                    issue=lit.publication.issue,
                    start_page=lit.publication.start_page,
                    end_page=lit.publication.end_page,
                    page_range=lit.publication.page_range,
                    article_number=lit.publication.article_number,
                )
                session.add(ap)

            await session.flush()
            await session.commit()
            return ArticleService._orm_to_schema(article)

    @staticmethod
    async def update(article_id: int, lit: LiteratureSchema) -> Optional[LiteratureSchema]:
        if not isinstance(lit, LiteratureSchema):
            raise TypeError("update expects a LiteratureSchema instance")
        async with DbSession() as session:
            q = select(Article).where(Article.id == article_id).with_for_update()
            res = await session.execute(q)
            article = res.scalar_one_or_none()
            if article is None:
                return None
            # update simple fields
            article.title = lit.article.title
            article.abstract = lit.article.abstract
            article.language = lit.article.language
            article.publication_year = lit.article.publication_year
            article.publication_date = lit.article.publication_date
            article.citation_count = lit.article.citation_count
            article.reference_count = lit.article.reference_count
            article.influential_citation_count = lit.article.influential_citation_count
            article.is_open_access = lit.article.is_open_access
            article.open_access_url = lit.article.open_access_url

            # naive replace identifiers: delete existing and insert new
            await session.execute(
                ArticleIdentifier.__table__.delete().where(ArticleIdentifier.article_id == article.id)
            )
            for ident in lit.identifiers:
                ai = ArticleIdentifier(
                    article_id=article.id,
                    identifier_type=ident.identifier_type,
                    identifier_value=ident.identifier_value,
                    is_primary=ident.is_primary,
                )
                session.add(ai)

            await session.flush()
            await session.commit()
            return ArticleService._orm_to_schema(article)

    @staticmethod
    async def delete(article_id: int) -> bool:
        async with DbSession() as session:
            q = select(Article).where(Article.id == article_id)
            res = await session.execute(q)
            article = res.scalar_one_or_none()
            if article is None:
                return False
            await session.delete(article)
            await session.commit()
            return True

    @staticmethod
    def _orm_to_schema(orm: Article) -> LiteratureSchema:
        art = ArticleSchema(
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
        authors: List[AuthorSchema] = []
        for aa in getattr(orm, 'authors', []) or []:
            # we only have author relation entries; fill minimal info
            authors.append(AuthorSchema(full_name="", author_order=aa.author_order, is_corresponding=aa.is_corresponding))

        identifiers: List[IdentifierSchema] = []
        for ident in getattr(orm, 'identifiers', []) or []:
            identifiers.append(IdentifierSchema(identifier_type=ident.identifier_type, identifier_value=ident.identifier_value, is_primary=ident.is_primary))

        publication = PublicationSchema()
        pubs = getattr(orm, 'publications', []) or []
        if pubs:
            p = pubs[0]
            publication = PublicationSchema(
                volume=p.volume,
                issue=p.issue,
                start_page=p.start_page,
                end_page=p.end_page,
                page_range=p.page_range,
                article_number=p.article_number,
            )

        return LiteratureSchema(article=art, authors=authors, identifiers=identifiers, publication=publication)
