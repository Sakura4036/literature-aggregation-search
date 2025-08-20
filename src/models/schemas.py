"""
Literature schema classes for standardized data representation.

This module provides dataclass-based schema classes for literature information,
based on the database design in docs/database_design.md.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union, Tuple
from datetime import datetime, date

from .enums import IdentifierType, VenueType, CategoryType, PublicationTypeSource


@dataclass
class ArticleSchema:
    """Schema for article basic information."""
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


@dataclass
class AuthorSchema:
    """Schema for author information."""
    full_name: str = ""
    last_name: Optional[str] = None
    fore_name: Optional[str] = None
    initials: Optional[str] = None
    orcid: Optional[str] = None
    semantic_scholar_id: Optional[str] = None
    affiliation: Optional[str] = None
    is_corresponding: bool = False
    author_order: Optional[int] = None


@dataclass
class VenueSchema:
    """Schema for publication venue information."""
    venue_name: str = ""
    venue_type: VenueType = VenueType.OTHER
    iso_abbreviation: Optional[str] = None
    issn_print: Optional[str] = None
    issn_electronic: Optional[str] = None
    publisher: Optional[str] = None
    country: Optional[str] = None


@dataclass
class PublicationSchema:
    """Schema for publication details."""
    volume: Optional[str] = None
    issue: Optional[str] = None
    start_page: Optional[str] = None
    end_page: Optional[str] = None
    page_range: Optional[str] = None
    article_number: Optional[str] = None


@dataclass
class IdentifierSchema:
    """Schema for article identifiers."""
    identifier_type: IdentifierType
    identifier_value: str
    is_primary: bool = False


@dataclass
class CategorySchema:
    """Schema for subject categories."""
    category_name: str
    category_code: Optional[str] = None
    category_type: CategoryType = CategoryType.OTHER
    is_major_topic: bool = False
    confidence_score: Optional[float] = None


@dataclass
class PublicationTypeSchema:
    """Schema for publication types."""
    type_name: str
    type_code: Optional[str] = None
    source_type: PublicationTypeSource = PublicationTypeSource.GENERAL


@dataclass
class LiteratureSchema:
    """
    Unified literature schema based on database_design.md.
    
    This class represents a complete literature record with all associated
    information including article details, authors, venue, identifiers, etc.
    """
    
    # Core information
    article: ArticleSchema = field(default_factory=ArticleSchema)
    authors: List[AuthorSchema] = field(default_factory=list)
    venue: VenueSchema = field(default_factory=VenueSchema)
    publication: PublicationSchema = field(default_factory=PublicationSchema)
    
    # Identifiers and classifications
    identifiers: List[IdentifierSchema] = field(default_factory=list)
    categories: List[CategorySchema] = field(default_factory=list)
    publication_types: List[PublicationTypeSchema] = field(default_factory=list)
    
    # Source data information
    source_specific: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate the literature schema data.
        
        Returns:
            Tuple[bool, List[str]]: (is_valid, error_messages)
        """
        errors = []
        
        # Required field validation
        if not self.article.title.strip():
            errors.append("Article title is required")
        
        # DOI format validation
        if self.article.primary_doi and not self._is_valid_doi(self.article.primary_doi):
            errors.append("Invalid DOI format")
        
        # Publication year validation
        if self.article.publication_year:
            current_year = datetime.now().year
            if self.article.publication_year < 1000 or self.article.publication_year > current_year + 5:
                errors.append("Invalid publication year")
        
        # Author information validation
        for i, author in enumerate(self.authors):
            if not author.full_name.strip():
                errors.append(f"Author {i+1} name is required")
        
        # Identifier validation
        for i, identifier in enumerate(self.identifiers):
            if not identifier.identifier_value or not identifier.identifier_value.strip():
                errors.append(f"Identifier {i+1} value is required")
        
        # Citation count validation
        if self.article.citation_count < 0:
            errors.append("Citation count cannot be negative")
        
        if self.article.reference_count < 0:
            errors.append("Reference count cannot be negative")
        
        return len(errors) == 0, errors
    
    def _is_valid_doi(self, doi: str) -> bool:
        """
        Validate DOI format.
        
        Args:
            doi: DOI string to validate
            
        Returns:
            bool: True if DOI format is valid
        """
        doi_pattern = r'^10\.\d{4,}/[^\s]+$'
        return bool(re.match(doi_pattern, doi))
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the schema to a dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the schema
        """
        from dataclasses import asdict
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LiteratureSchema':
        """
        Create a LiteratureSchema instance from a dictionary.
        
        Args:
            data: Dictionary containing schema data
            
        Returns:
            LiteratureSchema: New instance created from the dictionary
        """
        # Handle nested objects
        if 'article' in data and isinstance(data['article'], dict):
            data['article'] = ArticleSchema(**data['article'])
        
        if 'venue' in data and isinstance(data['venue'], dict):
            venue_data = data['venue'].copy()
            if 'venue_type' in venue_data and isinstance(venue_data['venue_type'], str):
                venue_data['venue_type'] = VenueType(venue_data['venue_type'])
            data['venue'] = VenueSchema(**venue_data)
        
        if 'publication' in data and isinstance(data['publication'], dict):
            data['publication'] = PublicationSchema(**data['publication'])
        
        # Handle list objects
        if 'authors' in data:
            data['authors'] = [
                AuthorSchema(**author) if isinstance(author, dict) else author 
                for author in data['authors']
            ]
        
        if 'identifiers' in data:
            identifiers = []
            for identifier in data['identifiers']:
                if isinstance(identifier, dict):
                    identifier_data = identifier.copy()
                    # Skip identifiers with None or empty values
                    if not identifier_data.get('identifier_value'):
                        continue
                    if 'identifier_type' in identifier_data and isinstance(identifier_data['identifier_type'], str):
                        identifier_data['identifier_type'] = IdentifierType(identifier_data['identifier_type'])
                    identifiers.append(IdentifierSchema(**identifier_data))
                else:
                    identifiers.append(identifier)
            data['identifiers'] = identifiers
        
        if 'categories' in data:
            categories = []
            for category in data['categories']:
                if isinstance(category, dict):
                    category_data = category.copy()
                    if 'category_type' in category_data and isinstance(category_data['category_type'], str):
                        category_data['category_type'] = CategoryType(category_data['category_type'])
                    categories.append(CategorySchema(**category_data))
                else:
                    categories.append(category)
            data['categories'] = categories
        
        if 'publication_types' in data:
            pub_types = []
            for pub_type in data['publication_types']:
                if isinstance(pub_type, dict):
                    pub_type_data = pub_type.copy()
                    if 'source_type' in pub_type_data and isinstance(pub_type_data['source_type'], str):
                        pub_type_data['source_type'] = PublicationTypeSource(pub_type_data['source_type'])
                    pub_types.append(PublicationTypeSchema(**pub_type_data))
                else:
                    pub_types.append(pub_type)
            data['publication_types'] = pub_types
        
        return cls(**data)
    
    def get_primary_identifier(self, identifier_type: IdentifierType) -> Optional[str]:
        """
        Get the primary identifier of a specific type.
        
        Args:
            identifier_type: Type of identifier to retrieve
            
        Returns:
            Optional[str]: The identifier value if found, None otherwise
        """
        for identifier in self.identifiers:
            if identifier.identifier_type == identifier_type and identifier.is_primary:
                return identifier.identifier_value
        return None
    
    def get_identifier(self, identifier_type: IdentifierType) -> Optional[str]:
        """
        Get any identifier of a specific type (primary or not).
        
        Args:
            identifier_type: Type of identifier to retrieve
            
        Returns:
            Optional[str]: The identifier value if found, None otherwise
        """
        for identifier in self.identifiers:
            if identifier.identifier_type == identifier_type:
                return identifier.identifier_value
        return None
    
    def add_identifier(self, identifier_type: IdentifierType, value: str, is_primary: bool = False):
        """
        Add an identifier to the literature record.
        
        Args:
            identifier_type: Type of the identifier
            value: Identifier value
            is_primary: Whether this is the primary identifier of this type
        """
        if value and value.strip():
            # Check if identifier already exists
            for existing in self.identifiers:
                if (existing.identifier_type == identifier_type and 
                    existing.identifier_value == value.strip()):
                    return  # Already exists
            
            self.identifiers.append(IdentifierSchema(
                identifier_type=identifier_type,
                identifier_value=value.strip(),
                is_primary=is_primary
            ))
    
    def add_author(self, full_name: str, **kwargs):
        """
        Add an author to the literature record.
        
        Args:
            full_name: Author's full name
            **kwargs: Additional author information
        """
        if full_name and full_name.strip():
            author_order = kwargs.get('author_order', len(self.authors) + 1)
            self.authors.append(AuthorSchema(
                full_name=full_name.strip(),
                author_order=author_order,
                **{k: v for k, v in kwargs.items() if k != 'author_order'}
            ))
    
    def add_category(self, category_name: str, category_type: CategoryType = CategoryType.OTHER, **kwargs):
        """
        Add a subject category to the literature record.
        
        Args:
            category_name: Name of the category
            category_type: Type of the category
            **kwargs: Additional category information
        """
        if category_name and category_name.strip():
            self.categories.append(CategorySchema(
                category_name=category_name.strip(),
                category_type=category_type,
                **kwargs
            ))
    
    def get_doi(self) -> Optional[str]:
        """Get the DOI identifier."""
        return self.get_identifier(IdentifierType.DOI)
    
    def get_pmid(self) -> Optional[str]:
        """Get the PMID identifier."""
        return self.get_identifier(IdentifierType.PMID)
    
    def get_arxiv_id(self) -> Optional[str]:
        """Get the ArXiv ID identifier."""
        return self.get_identifier(IdentifierType.ARXIV_ID)
    
    def __str__(self) -> str:
        """String representation of the literature record."""
        return f"LiteratureSchema(title='{self.article.title[:50]}...', authors={len(self.authors)})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the literature record."""
        return (f"LiteratureSchema(title='{self.article.title}', "
                f"authors={len(self.authors)}, "
                f"identifiers={len(self.identifiers)}, "
                f"source='{self.source_specific.get('source', 'unknown')}')")