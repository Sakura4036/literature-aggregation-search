"""Pydantic v2 schema models for literature data.

These models are intended for use with FastAPI request/response models
and for convenient conversion from SQLAlchemy ORM objects (via
``model_config = ConfigDict(from_attributes=True)``).
"""

import re
from typing import List, Optional, Dict, Any, Union, Tuple
from datetime import datetime, date

from pydantic import BaseModel, Field, ConfigDict, ValidationError, field_validator

from .enums import IdentifierType, VenueType, CategoryType, PublicationTypeSource


def _is_valid_doi(doi: str) -> bool:
    doi_pattern = r'^10\.\d{4,}/[^\s]+$'
    return bool(re.match(doi_pattern, doi))


class ArticleSchema(BaseModel):
    article_id: Optional[str] = None
    primary_doi: Optional[str] = None
    title: str = ""
    abstract: Optional[str] = None
    language: str = "eng"
    publication_year: Optional[int] = None
    publication_date: Optional[Union[str, date]] = None
    updated_date: Optional[Union[str, date]] = None
    citation_count: int = 0
    reference_count: int = 0
    influential_citation_count: int = 0
    is_open_access: bool = False
    open_access_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, validate_assignment=True)

    @field_validator('primary_doi')
    @classmethod
    def _validate_doi(cls, v):
        if v is None:
            return v
        if not _is_valid_doi(v):
            raise ValueError('Invalid DOI format')
        return v


class AuthorSchema(BaseModel):
    full_name: str = ""
    last_name: Optional[str] = None
    fore_name: Optional[str] = None
    initials: Optional[str] = None
    orcid: Optional[str] = None
    semantic_scholar_id: Optional[str] = None
    affiliation: Optional[str] = None
    is_corresponding: bool = False
    author_order: Optional[int] = None

    model_config = ConfigDict(from_attributes=True, validate_assignment=True)


class VenueSchema(BaseModel):
    venue_name: str = ""
    venue_type: VenueType = VenueType.OTHER
    iso_abbreviation: Optional[str] = None
    issn_print: Optional[str] = None
    issn_electronic: Optional[str] = None
    publisher: Optional[str] = None
    country: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, validate_assignment=True)


class PublicationSchema(BaseModel):
    volume: Optional[str] = None
    issue: Optional[str] = None
    start_page: Optional[str] = None
    end_page: Optional[str] = None
    page_range: Optional[str] = None
    article_number: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, validate_assignment=True)


class IdentifierSchema(BaseModel):
    identifier_type: IdentifierType
    identifier_value: str
    is_primary: bool = False

    model_config = ConfigDict(from_attributes=True, validate_assignment=True)

    @field_validator('identifier_value')
    @classmethod
    def _not_empty(cls, v):
        if not v or not str(v).strip():
            raise ValueError('identifier_value is required')
        return str(v).strip()


class CategorySchema(BaseModel):
    category_name: str
    category_code: Optional[str] = None
    category_type: CategoryType = CategoryType.OTHER
    is_major_topic: bool = False
    confidence_score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True, validate_assignment=True)


class PublicationTypeSchema(BaseModel):
    type_name: str
    type_code: Optional[str] = None
    source_type: PublicationTypeSource = PublicationTypeSource.GENERAL

    model_config = ConfigDict(from_attributes=True, validate_assignment=True)


class LiteratureSchema(BaseModel):
    article: ArticleSchema = Field(default_factory=ArticleSchema)
    authors: List[AuthorSchema] = Field(default_factory=list)
    venue: VenueSchema = Field(default_factory=VenueSchema)
    publication: PublicationSchema = Field(default_factory=PublicationSchema)

    identifiers: List[IdentifierSchema] = Field(default_factory=list)
    categories: List[CategorySchema] = Field(default_factory=list)
    publication_types: List[PublicationTypeSchema] = Field(default_factory=list)

    source_specific: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True, validate_assignment=True)

    def validate_schema(self) -> Tuple[bool, List[str]]:
        """Validate the literature schema fields and return (is_valid, errors)."""
        errors: List[str] = []

        if not self.article.title or not str(self.article.title).strip():
            errors.append('Article title is required')

        # publication year sanity
        if self.article.publication_year:
            current_year = datetime.now().year
            if self.article.publication_year < 1000 or self.article.publication_year > current_year + 5:
                errors.append('Invalid publication year')

        for i, author in enumerate(self.authors):
            if not author.full_name or not author.full_name.strip():
                errors.append(f'Author {i+1} name is required')

        for i, identifier in enumerate(self.identifiers):
            if not identifier.identifier_value or not identifier.identifier_value.strip():
                errors.append(f'Identifier {i+1} value is required')

        if self.article.citation_count < 0:
            errors.append('Citation count cannot be negative')

        if self.article.reference_count < 0:
            errors.append('Reference count cannot be negative')

        return (len(errors) == 0, errors)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LiteratureSchema':
        """Create a Literature instance from a plain dict, handling enum strings.

        This mirrors the previous dataclass-based from_dict behavior but uses
        Pydantic's validation and conversion where possible.
        """
        data = data.copy()

        # normalize nested dicts -> Pydantic will handle most cases but ensure enums are converted
        if 'venue' in data and isinstance(data['venue'], dict):
            v = data['venue'].copy()
            if 'venue_type' in v and isinstance(v['venue_type'], str):
                try:
                    v['venue_type'] = VenueType(v['venue_type'])
                except Exception:
                    pass
            data['venue'] = v

        if 'identifiers' in data:
            ids = []
            for identifier in data['identifiers']:
                if isinstance(identifier, dict):
                    idd = identifier.copy()
                    if 'identifier_type' in idd and isinstance(idd['identifier_type'], str):
                        try:
                            idd['identifier_type'] = IdentifierType(idd['identifier_type'])
                        except Exception:
                            pass
                    ids.append(idd)
                else:
                    ids.append(identifier)
            data['identifiers'] = ids

        if 'categories' in data:
            cats = []
            for category in data['categories']:
                if isinstance(category, dict):
                    cd = category.copy()
                    if 'category_type' in cd and isinstance(cd['category_type'], str):
                        try:
                            cd['category_type'] = CategoryType(cd['category_type'])
                        except Exception:
                            pass
                    cats.append(cd)
                else:
                    cats.append(category)
            data['categories'] = cats

        if 'publication_types' in data:
            pts = []
            for pt in data['publication_types']:
                if isinstance(pt, dict):
                    pd = pt.copy()
                    if 'source_type' in pd and isinstance(pd['source_type'], str):
                        try:
                            pd['source_type'] = PublicationTypeSource(pd['source_type'])
                        except Exception:
                            pass
                    pts.append(pd)
                else:
                    pts.append(pt)
            data['publication_types'] = pts

        try:
            return cls.model_validate(data)
        except ValidationError as exc:
            # re-raise for callers or allow them to catch; keep message concise
            raise

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    def get_primary_identifier(self, identifier_type: IdentifierType) -> Optional[str]:
        for identifier in self.identifiers:
            if identifier.identifier_type == identifier_type and identifier.is_primary:
                return identifier.identifier_value
        return None

    def get_identifier(self, identifier_type: IdentifierType) -> Optional[str]:
        for identifier in self.identifiers:
            if identifier.identifier_type == identifier_type:
                return identifier.identifier_value
        return None

    def add_identifier(self, identifier_type: IdentifierType, value: str, is_primary: bool = False):
        if value and value.strip():
            for existing in self.identifiers:
                if existing.identifier_type == identifier_type and existing.identifier_value == value.strip():
                    return
            self.identifiers.append(IdentifierSchema(identifier_type=identifier_type, identifier_value=value.strip(), is_primary=is_primary))

    def add_author(self, full_name: str, **kwargs):
        if full_name and full_name.strip():
            author_order = kwargs.get('author_order', len(self.authors) + 1)
            d = {k: v for k, v in kwargs.items() if k != 'author_order'}
            self.authors.append(AuthorSchema(full_name=full_name.strip(), author_order=author_order, **d))

    def add_category(self, category_name: str, category_type: CategoryType = CategoryType.OTHER, **kwargs):
        if category_name and category_name.strip():
            self.categories.append(CategorySchema(category_name=category_name.strip(), category_type=category_type, **kwargs))

    def get_doi(self) -> Optional[str]:
        return self.get_identifier(IdentifierType.DOI)

    def get_pmid(self) -> Optional[str]:
        return self.get_identifier(IdentifierType.PMID)

    def get_arxiv_id(self) -> Optional[str]:
        return self.get_identifier(IdentifierType.ARXIV_ID)

    def __str__(self) -> str:
        title = (self.article.title or '')[:50]
        return f"Literature(title='{title}...', authors={len(self.authors)})"

    def __repr__(self) -> str:
        return (f"Literature(title='{self.article.title}', authors={len(self.authors)}, "
                f"identifiers={len(self.identifiers)}, source='{self.source_specific.get('source', 'unknown')}')")