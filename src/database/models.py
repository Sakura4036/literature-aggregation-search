"""
SQLAlchemy ORM models for the literature database.

This module defines the database table structures using SQLAlchemy's declarative base,
based on the design specified in `docs/database_design.md`.
All models use UUID primary keys for global uniqueness.
"""

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Date, DateTime,
    ForeignKey, SmallInteger, Enum, UniqueConstraint, Index, DECIMAL,
    DDL, event
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

from src.models.enums import IdentifierType, VenueType, CategoryType, PublicationTypeSource
from src.database.mixins import UUIDMixin, TimestampMixin

Base = declarative_base()

class Article(Base, UUIDMixin, TimestampMixin):
    """Article model representing literature articles with UUID primary key."""
    __tablename__ = 'articles'

    primary_doi = Column(String(255), unique=True)
    title = Column(Text, nullable=False)
    abstract = Column(Text)
    language = Column(String(10), default='eng')
    publication_year = Column(Integer)
    publication_date = Column(Date)
    updated_date = Column(Date)
    citation_count = Column(Integer, default=0)
    reference_count = Column(Integer, default=0)
    influential_citation_count = Column(Integer, default=0)
    is_open_access = Column(Boolean, default=False)
    open_access_url = Column(Text)

    # Relationships
    sources = relationship("ArticleSource", back_populates="article", cascade="all, delete-orphan")
    identifiers = relationship("ArticleIdentifier", back_populates="article", cascade="all, delete-orphan")
    publications = relationship("ArticlePublication", back_populates="article", cascade="all, delete-orphan")
    authors = relationship("ArticleAuthor", back_populates="article", cascade="all, delete-orphan")
    categories = relationship("ArticleCategory", back_populates="article", cascade="all, delete-orphan")
    publication_types_assoc = relationship("ArticlePublicationType", back_populates="article", cascade="all, delete-orphan")
    funding = relationship("ArticleFunding", back_populates="article", cascade="all, delete-orphan")
    citations_made = relationship("Citation", foreign_keys="[Citation.citing_article_id]", back_populates="citing_article", cascade="all, delete-orphan")
    citations_received = relationship("Citation", foreign_keys="[Citation.cited_article_id]", back_populates="cited_article", cascade="all, delete-orphan")
    abstract_sections = relationship("AbstractSection", back_populates="article", cascade="all, delete-orphan")
    versions = relationship("ArticleVersion", back_populates="article", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_articles_publication_year', 'publication_year'),
        Index('idx_articles_publication_date', 'publication_date'),
        Index('idx_articles_citation_count', 'citation_count'),
        Index('idx_articles_primary_doi', 'primary_doi'),
    )

event.listen(
    Article.__table__,
    'after_create',
    DDL("""
    CREATE INDEX idx_articles_title ON articles USING gin(to_tsvector('english', title));
    CREATE INDEX idx_articles_abstract ON articles USING gin(to_tsvector('english', abstract));
    CREATE INDEX idx_articles_fulltext ON articles USING gin(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(abstract, '')));
    """).execute_if(dialect='postgresql')
)

class DataSource(Base, UUIDMixin, TimestampMixin):
    """Data source model for tracking literature sources with UUID primary key."""
    __tablename__ = 'data_sources'

    source_name = Column(String(50), nullable=False, unique=True)
    source_url = Column(String(200))
    description = Column(Text)
    is_active = Column(Boolean, default=True)

    articles = relationship("ArticleSource", back_populates="source")

    __table_args__ = (
        Index('idx_data_sources_name', 'source_name'),
    )

class ArticleSource(Base, UUIDMixin, TimestampMixin):
    """Article source association model with UUID primary key."""
    __tablename__ = 'article_sources'

    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id', ondelete='CASCADE'), nullable=False)
    source_id = Column(UUID(as_uuid=True), ForeignKey('data_sources.id'), nullable=False)
    source_article_id = Column(String(100))
    source_url = Column(Text)
    raw_data = Column(JSONB)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    article = relationship("Article", back_populates="sources")
    source = relationship("DataSource", back_populates="articles")

    __table_args__ = (
        UniqueConstraint('article_id', 'source_id', name='uq_article_source'),
        Index('idx_article_sources_article_id', 'article_id'),
        Index('idx_article_sources_source_id', 'source_id'),
        Index('idx_article_sources_source_article_id', 'source_article_id'),
        Index('idx_article_sources_raw_data', 'raw_data', postgresql_using='gin'),
    )

class ArticleIdentifier(Base, UUIDMixin):
    """Article identifier model with UUID primary key."""
    __tablename__ = 'article_identifiers'

    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id', ondelete='CASCADE'), nullable=False)
    identifier_type = Column(Enum(IdentifierType), nullable=False)
    identifier_value = Column(String(200), nullable=False)
    is_primary = Column(Boolean, default=False)

    article = relationship("Article", back_populates="identifiers")

    __table_args__ = (
        UniqueConstraint('identifier_type', 'identifier_value', name='uq_identifier_type_value'),
        Index('idx_article_identifiers_article_id', 'article_id'),
        Index('idx_article_identifiers_value', 'identifier_value'),
        Index('idx_article_identifiers_type_value', 'identifier_type', 'identifier_value'),
    )

class Venue(Base, UUIDMixin, TimestampMixin):
    """Venue model for publication venues with UUID primary key."""
    __tablename__ = 'venues'

    venue_name = Column(String(500), nullable=False)
    venue_type = Column(Enum(VenueType), default=VenueType.JOURNAL)
    iso_abbreviation = Column(String(200))
    issn_print = Column(String(20))
    issn_electronic = Column(String(20))
    publisher = Column(String(200))
    country = Column(String(100))

    publications = relationship("ArticlePublication", back_populates="venue")

    __table_args__ = (
        Index('idx_venue_name', 'venue_name'),
        Index('idx_venue_type', 'venue_type'),
    )

class ArticlePublication(Base, UUIDMixin):
    """Article publication details model with UUID primary key."""
    __tablename__ = 'article_publications'

    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id', ondelete='CASCADE'), nullable=False)
    venue_id = Column(UUID(as_uuid=True), ForeignKey('venues.id'))
    volume = Column(String(50))
    issue = Column(String(50))
    start_page = Column(String(20))
    end_page = Column(String(20))
    page_range = Column(String(50))
    article_number = Column(String(50))
    pub_model = Column(String(100))

    article = relationship("Article", back_populates="publications")
    venue = relationship("Venue", back_populates="publications")

    __table_args__ = (
        Index('idx_ap_article_id', 'article_id'),
        Index('idx_ap_venue_id', 'venue_id'),
    )

class Author(Base, UUIDMixin, TimestampMixin):
    """Author model with UUID primary key."""
    __tablename__ = 'authors'

    full_name = Column(String(200), nullable=False)
    last_name = Column(String(100))
    fore_name = Column(String(100))
    initials = Column(String(20))
    orcid = Column(String(100))
    semantic_scholar_id = Column(String(50))
    h_index = Column(Integer)
    paper_count = Column(Integer)
    citation_count = Column(Integer)
    homepage = Column(String(500))

    articles = relationship("ArticleAuthor", back_populates="author")

    __table_args__ = (
        Index('idx_author_full_name', 'full_name'),
        Index('idx_author_orcid', 'orcid', unique=True),
        Index('idx_author_semantic_scholar_id', 'semantic_scholar_id', unique=True),
    )

class Affiliation(Base, UUIDMixin):
    """Affiliation model with UUID primary key."""
    __tablename__ = 'affiliations'

    name = Column(Text, nullable=False)
    country = Column(String(100))
    ror_id = Column(String(100), unique=True)

    authors = relationship("ArticleAuthor", back_populates="affiliation")

    __table_args__ = (
        Index('idx_affiliation_name', 'name'),
        Index('idx_affiliation_ror_id', 'ror_id'),
    )

class ArticleAuthor(Base, UUIDMixin):
    """Article-Author association model with UUID primary key."""
    __tablename__ = 'article_authors'

    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id', ondelete='CASCADE'), nullable=False)
    author_id = Column(UUID(as_uuid=True), ForeignKey('authors.id', ondelete='CASCADE'), nullable=False)
    affiliation_id = Column(UUID(as_uuid=True), ForeignKey('affiliations.id'))
    author_order = Column(SmallInteger, nullable=False)
    is_corresponding = Column(Boolean, default=False)

    article = relationship("Article", back_populates="authors")
    author = relationship("Author", back_populates="articles")
    affiliation = relationship("Affiliation", back_populates="authors")

    __table_args__ = (
        UniqueConstraint('article_id', 'author_order', name='uq_article_author_order'),
        Index('idx_aa_article_id', 'article_id'),
        Index('idx_aa_author_id', 'author_id'),
    )

class SubjectCategory(Base, UUIDMixin, TimestampMixin):
    """Subject category model with UUID primary key."""
    __tablename__ = 'subject_categories'

    category_name = Column(String(200), nullable=False)
    category_code = Column(String(50))
    category_type = Column(Enum(CategoryType), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey('subject_categories.id'))
    description = Column(Text)

    parent = relationship("SubjectCategory", remote_side="SubjectCategory.id")
    articles = relationship("ArticleCategory", back_populates="category")

    __table_args__ = (
        Index('idx_sc_category_name', 'category_name'),
        Index('idx_sc_category_type', 'category_type'),
    )

class ArticleCategory(Base, UUIDMixin):
    """Article-Category association model with UUID primary key."""
    __tablename__ = 'article_categories'

    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id', ondelete='CASCADE'), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey('subject_categories.id', ondelete='CASCADE'), nullable=False)
    is_major_topic = Column(Boolean, default=False)
    confidence_score = Column(DECIMAL(3, 2))

    article = relationship("Article", back_populates="categories")
    category = relationship("SubjectCategory", back_populates="articles")
    mesh_qualifiers = relationship("ArticleMeshQualifier", back_populates="article_category", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('article_id', 'category_id', name='uq_article_category'),
        Index('idx_ac_article_id', 'article_id'),
        Index('idx_ac_category_id', 'category_id'),
    )

class MeshQualifier(Base, UUIDMixin, TimestampMixin):
    """MeSH qualifier model with UUID primary key."""
    __tablename__ = 'mesh_qualifiers'

    qualifier_name = Column(String(200), nullable=False)
    qualifier_ui = Column(String(20), nullable=False, unique=True)

    article_categories = relationship("ArticleMeshQualifier", back_populates="mesh_qualifier")

    __table_args__ = (
        Index('idx_mq_qualifier_name', 'qualifier_name'),
    )

class ArticleMeshQualifier(Base, UUIDMixin):
    """Article-MeshQualifier association model with UUID primary key."""
    __tablename__ = 'article_mesh_qualifiers'

    article_category_id = Column(UUID(as_uuid=True), ForeignKey('article_categories.id', ondelete='CASCADE'), nullable=False)
    mesh_qualifier_id = Column(UUID(as_uuid=True), ForeignKey('mesh_qualifiers.id', ondelete='CASCADE'), nullable=False)
    is_major_topic = Column(Boolean, default=False)

    article_category = relationship("ArticleCategory", back_populates="mesh_qualifiers")
    mesh_qualifier = relationship("MeshQualifier", back_populates="article_categories")

    __table_args__ = (
        UniqueConstraint('article_category_id', 'mesh_qualifier_id', name='uq_category_qualifier'),
    )

class PublicationType(Base, UUIDMixin, TimestampMixin):
    """Publication type model with UUID primary key."""
    __tablename__ = 'publication_types'

    type_name = Column(String(200), nullable=False)
    type_code = Column(String(50))
    source_type = Column(Enum(PublicationTypeSource), default=PublicationTypeSource.GENERAL)
    description = Column(Text)

    articles = relationship("ArticlePublicationType", back_populates="publication_type")

    __table_args__ = (
        Index('idx_pt_type_name', 'type_name'),
        Index('idx_pt_source_type', 'source_type'),
    )

class ArticlePublicationType(Base, UUIDMixin):
    """Article-PublicationType association model with UUID primary key."""
    __tablename__ = 'article_publication_types'

    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id', ondelete='CASCADE'), nullable=False)
    publication_type_id = Column(UUID(as_uuid=True), ForeignKey('publication_types.id', ondelete='CASCADE'), nullable=False)

    article = relationship("Article", back_populates="publication_types_assoc")
    publication_type = relationship("PublicationType", back_populates="articles")

    __table_args__ = (
        UniqueConstraint('article_id', 'publication_type_id', name='uq_article_pub_type'),
    )

class FundingAgency(Base, UUIDMixin, TimestampMixin):
    """Funding agency model with UUID primary key."""
    __tablename__ = 'funding_agencies'

    agency_name = Column(String(200), nullable=False)
    acronym = Column(String(50))
    country = Column(String(100))
    ror_id = Column(String(100))

    articles = relationship("ArticleFunding", back_populates="funding_agency")

    __table_args__ = (
        Index('idx_fa_agency_name', 'agency_name'),
        Index('idx_fa_ror_id', 'ror_id', unique=True),
    )

class ArticleFunding(Base, UUIDMixin):
    """Article-Funding association model with UUID primary key."""
    __tablename__ = 'article_funding'

    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id', ondelete='CASCADE'), nullable=False)
    funding_agency_id = Column(UUID(as_uuid=True), ForeignKey('funding_agencies.id', ondelete='CASCADE'), nullable=False)
    grant_id = Column(String(100))
    award_id = Column(String(100))

    article = relationship("Article", back_populates="funding")
    funding_agency = relationship("FundingAgency", back_populates="articles")

    __table_args__ = (
        Index('idx_af_article_id', 'article_id'),
        Index('idx_af_funding_agency_id', 'funding_agency_id'),
    )

class Citation(Base, UUIDMixin):
    """Citation model with UUID primary key."""
    __tablename__ = 'citations'

    citing_article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id', ondelete='CASCADE'), nullable=False)
    cited_article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id', ondelete='SET NULL'))
    cited_paper_title = Column(Text)
    cited_paper_info = Column(Text)
    citation_context = Column(Text)
    is_influential = Column(Boolean, default=False)

    citing_article = relationship("Article", foreign_keys=[citing_article_id], back_populates="citations_made")
    cited_article = relationship("Article", foreign_keys=[cited_article_id], back_populates="citations_received")

    __table_args__ = (
        Index('idx_cit_citing_article_id', 'citing_article_id'),
        Index('idx_cit_cited_article_id', 'cited_article_id'),
    )

class AbstractSection(Base, UUIDMixin):
    """Abstract section model with UUID primary key."""
    __tablename__ = 'abstract_sections'

    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id', ondelete='CASCADE'), nullable=False)
    section_label = Column(String(100))
    section_text = Column(Text, nullable=False)
    section_order = Column(SmallInteger, nullable=False)

    article = relationship("Article", back_populates="abstract_sections")

    __table_args__ = (
        UniqueConstraint('article_id', 'section_order', name='uq_article_section_order'),
    )

class ArticleVersion(Base, UUIDMixin):
    """Article version model with UUID primary key."""
    __tablename__ = 'article_versions'

    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id', ondelete='CASCADE'), nullable=False)
    version_number = Column(String(10), nullable=False)
    version_date = Column(Date)
    version_comment = Column(Text)
    pdf_url = Column(Text)

    article = relationship("Article", back_populates="versions")

    __table_args__ = (
        UniqueConstraint('article_id', 'version_number', name='uq_article_version'),
    )
