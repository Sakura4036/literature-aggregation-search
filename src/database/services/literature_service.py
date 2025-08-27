from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schemas import LiteratureSchema, ArticleSchema, AuthorSchema, IdentifierSchema, PublicationSchema, VenueSchema,CategorySchema, PublicationTypeSchema
from . import author_service, venue_service, identifier_service, publication_type_service, subject_category_service
from .article_service import ArticleService
from src.database.models import Article, ArticleIdentifier, ArticleAuthor, ArticlePublication
from src.models.enums import IdentifierType
from src.database.connection import DbSession


def article_to_literature_schema(article: Article) -> LiteratureSchema:
    return LiteratureSchema(
        article=ArticleSchema(**article.__dict__),
        authors=[AuthorSchema(**a.author.__dict__) for a in article.authors],
        venue=VenueSchema(**article.publications[0].venue.__dict__) if article.publications else VenueSchema(),
        publication=PublicationSchema(**article.publications[0].__dict__) if article.publications else PublicationSchema(),
        identifiers=[IdentifierSchema(**i.__dict__) for i in article.identifiers],
        categories=[CategorySchema(**c.__dict__) for c in article.categories],
        publication_types=[PublicationTypeSchema(**pt.__dict__) for pt in article.publication_types_assoc],
        source_specific={}
    )

class LiteratureService:
    @staticmethod
    async def get_literature_by_id(id: int, id_type="article", session: AsyncSession=DbSession) -> Optional[LiteratureSchema]:
        match id_type.lower():
            case "article":
                q = select(Article).where(Article.id == id)
            case IdentifierType.DOI.value:
                q = select(Article).where(Article.primary_doi == id)
            case IdentifierType.PMID:
                q = select(Article).join(ArticleIdentifier).where(ArticleIdentifier.identifier_type == IdentifierType.PMID, ArticleIdentifier.identifier_value == id)
            case IdentifierType.ARXIV_ID:
                q = select(Article).join(ArticleIdentifier).where(ArticleIdentifier.identifier_type == IdentifierType.ARXIV_ID, ArticleIdentifier.identifier_value == id)
            case IdentifierType.SEMANTIC_SCHOLAR_ID: 
                q = select(Article).join(ArticleIdentifier).where(ArticleIdentifier.identifier_type == IdentifierType.SEMANTIC_SCHOLAR_ID, ArticleIdentifier.identifier_value == id)
            case IdentifierType.WOS_UID:
                q = select(Article).join(ArticleIdentifier).where(ArticleIdentifier.identifier_type == IdentifierType.WOS_UID, ArticleIdentifier.identifier_value == id)
            case _:
                raise ValueError(f"Unsupported id_type: {id_type}")
        res = await session.execute(q)
        orm = res.scalar_one_or_none()
        if orm is None:
            return None
        return article_to_literature_schema(orm)

    @staticmethod
    async def insert_literature(lit: LiteratureSchema, session: AsyncSession) -> LiteratureSchema:
        """Insert literature-level data. This function keeps single-entity services focused by orchestrating them.

        - Validates literature via validate_schema()
        - Creates Article row via article_service.create_article
        - Creates identifiers, authors, publication relations using dedicated services
        """
        if not isinstance(lit, LiteratureSchema):
            raise TypeError("insert_literature expects LiteratureSchema")

        valid, errors = lit.validate_schema()
        if not valid:
            # Caller can catch ValueError and turn into HTTP responses
            raise ValueError(f"Literature validation failed: {errors}")

        # Create article entity
        article_schema: ArticleSchema = await ArticleService.add_article(lit.article, session)

        # create identifiers
        for ident in lit.identifiers:
            await identifier_service.create(session=session, article_id=getattr(article_schema, 'id', None), ident=ident)

        # authors
        for a in lit.authors:
            author_id = await author_service.get_or_create_by_name_or_orcid(a, session=session)
            # create relation table entry
            aa = ArticleAuthor(article_id=article_schema_dict_id(article_schema), author_id=author_id, author_order=(a.author_order or 1), is_corresponding=a.is_corresponding)
            session.add(aa)

        # publication & venue
        if lit.venue and lit.venue.venue_name:
            venue_id = await venue_service.get_or_create(lit.venue, session=session)
        else:
            venue_id = None
        if lit.publication and (lit.publication.volume or lit.publication.issue or lit.publication.article_number or venue_id):
            ap = ArticlePublication(article_id=article_schema_dict_id(article_schema), venue_id=venue_id, volume=lit.publication.volume, issue=lit.publication.issue, start_page=lit.publication.start_page, end_page=lit.publication.end_page, page_range=lit.publication.page_range, article_number=lit.publication.article_number)
            session.add(ap)

        # commit orchestration
        async with session.begin():
            await session.flush()

        return lit



def article_schema_dict_id(article_schema: ArticleSchema) -> Optional[int]:
    # helper to extract id if present on ArticleSchema (some flows may attach it)
    return getattr(article_schema, 'id', None)
