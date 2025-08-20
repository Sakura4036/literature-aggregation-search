"""
Unit tests for literature schema classes.
"""

import pytest
from datetime import date, datetime
from src.models.schemas import (
    ArticleSchema, AuthorSchema, VenueSchema, PublicationSchema,
    IdentifierSchema, CategorySchema, PublicationTypeSchema, LiteratureSchema
)
from src.models.enums import IdentifierType, VenueType, CategoryType, PublicationTypeSource


class TestArticleSchema:
    """Test cases for ArticleSchema."""
    
    def test_article_schema_defaults(self):
        """Test ArticleSchema with default values."""
        article = ArticleSchema()
        assert article.primary_doi is None
        assert article.title == ""
        assert article.abstract is None
        assert article.language == "eng"
        assert article.publication_year is None
        assert article.citation_count == 0
        assert article.reference_count == 0
        assert article.is_open_access is False
    
    def test_article_schema_with_values(self):
        """Test ArticleSchema with provided values."""
        article = ArticleSchema(
            primary_doi="10.1000/test",
            title="Test Article",
            abstract="Test abstract",
            publication_year=2023,
            citation_count=10,
            is_open_access=True
        )
        assert article.primary_doi == "10.1000/test"
        assert article.title == "Test Article"
        assert article.abstract == "Test abstract"
        assert article.publication_year == 2023
        assert article.citation_count == 10
        assert article.is_open_access is True


class TestAuthorSchema:
    """Test cases for AuthorSchema."""
    
    def test_author_schema_defaults(self):
        """Test AuthorSchema with default values."""
        author = AuthorSchema()
        assert author.full_name == ""
        assert author.last_name is None
        assert author.fore_name is None
        assert author.orcid is None
        assert author.is_corresponding is False
        assert author.author_order is None
    
    def test_author_schema_with_values(self):
        """Test AuthorSchema with provided values."""
        author = AuthorSchema(
            full_name="John Doe",
            last_name="Doe",
            fore_name="John",
            orcid="0000-0000-0000-0000",
            is_corresponding=True,
            author_order=1
        )
        assert author.full_name == "John Doe"
        assert author.last_name == "Doe"
        assert author.fore_name == "John"
        assert author.orcid == "0000-0000-0000-0000"
        assert author.is_corresponding is True
        assert author.author_order == 1


class TestVenueSchema:
    """Test cases for VenueSchema."""
    
    def test_venue_schema_defaults(self):
        """Test VenueSchema with default values."""
        venue = VenueSchema()
        assert venue.venue_name == ""
        assert venue.venue_type == VenueType.OTHER
        assert venue.iso_abbreviation is None
        assert venue.issn_print is None
        assert venue.issn_electronic is None
    
    def test_venue_schema_with_values(self):
        """Test VenueSchema with provided values."""
        venue = VenueSchema(
            venue_name="Nature",
            venue_type=VenueType.JOURNAL,
            iso_abbreviation="Nature",
            issn_print="0028-0836",
            issn_electronic="1476-4687"
        )
        assert venue.venue_name == "Nature"
        assert venue.venue_type == VenueType.JOURNAL
        assert venue.iso_abbreviation == "Nature"
        assert venue.issn_print == "0028-0836"
        assert venue.issn_electronic == "1476-4687"


class TestIdentifierSchema:
    """Test cases for IdentifierSchema."""
    
    def test_identifier_schema_required_fields(self):
        """Test IdentifierSchema with required fields."""
        identifier = IdentifierSchema(
            identifier_type=IdentifierType.DOI,
            identifier_value="10.1000/test"
        )
        assert identifier.identifier_type == IdentifierType.DOI
        assert identifier.identifier_value == "10.1000/test"
        assert identifier.is_primary is False
    
    def test_identifier_schema_with_primary(self):
        """Test IdentifierSchema with primary flag."""
        identifier = IdentifierSchema(
            identifier_type=IdentifierType.DOI,
            identifier_value="10.1000/test",
            is_primary=True
        )
        assert identifier.is_primary is True


class TestCategorySchema:
    """Test cases for CategorySchema."""
    
    def test_category_schema_defaults(self):
        """Test CategorySchema with default values."""
        category = CategorySchema(category_name="Machine Learning")
        assert category.category_name == "Machine Learning"
        assert category.category_code is None
        assert category.category_type == CategoryType.OTHER
        assert category.is_major_topic is False
        assert category.confidence_score is None
    
    def test_category_schema_with_values(self):
        """Test CategorySchema with provided values."""
        category = CategorySchema(
            category_name="Machine Learning",
            category_code="ML001",
            category_type=CategoryType.FIELD_OF_STUDY,
            is_major_topic=True,
            confidence_score=0.95
        )
        assert category.category_name == "Machine Learning"
        assert category.category_code == "ML001"
        assert category.category_type == CategoryType.FIELD_OF_STUDY
        assert category.is_major_topic is True
        assert category.confidence_score == 0.95


class TestLiteratureSchema:
    """Test cases for LiteratureSchema."""
    
    def test_literature_schema_defaults(self):
        """Test LiteratureSchema with default values."""
        literature = LiteratureSchema()
        assert isinstance(literature.article, ArticleSchema)
        assert isinstance(literature.authors, list)
        assert len(literature.authors) == 0
        assert isinstance(literature.venue, VenueSchema)
        assert isinstance(literature.identifiers, list)
        assert len(literature.identifiers) == 0
        assert isinstance(literature.source_specific, dict)
    
    def test_literature_schema_validation_valid(self):
        """Test validation with valid data."""
        literature = LiteratureSchema()
        literature.article.title = "Test Article"
        literature.article.primary_doi = "10.1000/test"
        literature.article.publication_year = 2023
        literature.add_author("John Doe")
        
        is_valid, errors = literature.validate()
        assert is_valid is True
        assert len(errors) == 0
    
    def test_literature_schema_validation_missing_title(self):
        """Test validation with missing title."""
        literature = LiteratureSchema()
        
        is_valid, errors = literature.validate()
        assert is_valid is False
        assert "Article title is required" in errors
    
    def test_literature_schema_validation_invalid_doi(self):
        """Test validation with invalid DOI."""
        literature = LiteratureSchema()
        literature.article.title = "Test Article"
        literature.article.primary_doi = "invalid-doi"
        
        is_valid, errors = literature.validate()
        assert is_valid is False
        assert "Invalid DOI format" in errors
    
    def test_literature_schema_validation_invalid_year(self):
        """Test validation with invalid publication year."""
        literature = LiteratureSchema()
        literature.article.title = "Test Article"
        literature.article.publication_year = 999  # Too old
        
        is_valid, errors = literature.validate()
        assert is_valid is False
        assert "Invalid publication year" in errors
    
    def test_literature_schema_validation_negative_citations(self):
        """Test validation with negative citation count."""
        literature = LiteratureSchema()
        literature.article.title = "Test Article"
        literature.article.citation_count = -1
        
        is_valid, errors = literature.validate()
        assert is_valid is False
        assert "Citation count cannot be negative" in errors
    
    def test_doi_validation_valid(self):
        """Test DOI validation with valid DOIs."""
        literature = LiteratureSchema()
        
        assert literature._is_valid_doi("10.1000/test") is True
        assert literature._is_valid_doi("10.1038/nature12373") is True
        assert literature._is_valid_doi("10.1016/j.cell.2023.01.001") is True
    
    def test_doi_validation_invalid(self):
        """Test DOI validation with invalid DOIs."""
        literature = LiteratureSchema()
        
        assert literature._is_valid_doi("invalid-doi") is False
        assert literature._is_valid_doi("10.") is False
        assert literature._is_valid_doi("not-a-doi") is False
        assert literature._is_valid_doi("") is False
    
    def test_add_identifier(self):
        """Test adding identifiers."""
        literature = LiteratureSchema()
        
        literature.add_identifier(IdentifierType.DOI, "10.1000/test", is_primary=True)
        literature.add_identifier(IdentifierType.PMID, "12345678")
        
        assert len(literature.identifiers) == 2
        assert literature.identifiers[0].identifier_type == IdentifierType.DOI
        assert literature.identifiers[0].identifier_value == "10.1000/test"
        assert literature.identifiers[0].is_primary is True
        assert literature.identifiers[1].identifier_type == IdentifierType.PMID
        assert literature.identifiers[1].is_primary is False
    
    def test_add_identifier_duplicate(self):
        """Test adding duplicate identifiers."""
        literature = LiteratureSchema()
        
        literature.add_identifier(IdentifierType.DOI, "10.1000/test")
        literature.add_identifier(IdentifierType.DOI, "10.1000/test")  # Duplicate
        
        assert len(literature.identifiers) == 1  # Should not add duplicate
    
    def test_add_identifier_empty_value(self):
        """Test adding identifier with empty value."""
        literature = LiteratureSchema()
        
        literature.add_identifier(IdentifierType.DOI, "")
        literature.add_identifier(IdentifierType.DOI, "   ")  # Whitespace only
        
        assert len(literature.identifiers) == 0  # Should not add empty values
    
    def test_get_identifier(self):
        """Test getting identifiers by type."""
        literature = LiteratureSchema()
        
        literature.add_identifier(IdentifierType.DOI, "10.1000/test")
        literature.add_identifier(IdentifierType.PMID, "12345678")
        
        assert literature.get_identifier(IdentifierType.DOI) == "10.1000/test"
        assert literature.get_identifier(IdentifierType.PMID) == "12345678"
        assert literature.get_identifier(IdentifierType.ARXIV_ID) is None
    
    def test_get_primary_identifier(self):
        """Test getting primary identifiers."""
        literature = LiteratureSchema()
        
        literature.add_identifier(IdentifierType.DOI, "10.1000/test", is_primary=True)
        literature.add_identifier(IdentifierType.DOI, "10.1000/other", is_primary=False)
        
        assert literature.get_primary_identifier(IdentifierType.DOI) == "10.1000/test"
    
    def test_convenience_methods(self):
        """Test convenience methods for common identifiers."""
        literature = LiteratureSchema()
        
        literature.add_identifier(IdentifierType.DOI, "10.1000/test")
        literature.add_identifier(IdentifierType.PMID, "12345678")
        literature.add_identifier(IdentifierType.ARXIV_ID, "2301.00001")
        
        assert literature.get_doi() == "10.1000/test"
        assert literature.get_pmid() == "12345678"
        assert literature.get_arxiv_id() == "2301.00001"
    
    def test_add_author(self):
        """Test adding authors."""
        literature = LiteratureSchema()
        
        literature.add_author("John Doe", orcid="0000-0000-0000-0000", is_corresponding=True)
        literature.add_author("Jane Smith")
        
        assert len(literature.authors) == 2
        assert literature.authors[0].full_name == "John Doe"
        assert literature.authors[0].orcid == "0000-0000-0000-0000"
        assert literature.authors[0].is_corresponding is True
        assert literature.authors[0].author_order == 1
        assert literature.authors[1].full_name == "Jane Smith"
        assert literature.authors[1].author_order == 2
    
    def test_add_author_empty_name(self):
        """Test adding author with empty name."""
        literature = LiteratureSchema()
        
        literature.add_author("")
        literature.add_author("   ")  # Whitespace only
        
        assert len(literature.authors) == 0  # Should not add empty names
    
    def test_add_category(self):
        """Test adding categories."""
        literature = LiteratureSchema()
        
        literature.add_category("Machine Learning", CategoryType.FIELD_OF_STUDY, is_major_topic=True)
        literature.add_category("Computer Science")
        
        assert len(literature.categories) == 2
        assert literature.categories[0].category_name == "Machine Learning"
        assert literature.categories[0].category_type == CategoryType.FIELD_OF_STUDY
        assert literature.categories[0].is_major_topic is True
        assert literature.categories[1].category_name == "Computer Science"
        assert literature.categories[1].category_type == CategoryType.OTHER
    
    def test_to_dict(self):
        """Test converting to dictionary."""
        literature = LiteratureSchema()
        literature.article.title = "Test Article"
        literature.add_author("John Doe")
        literature.add_identifier(IdentifierType.DOI, "10.1000/test")
        
        data = literature.to_dict()
        
        assert isinstance(data, dict)
        assert data['article']['title'] == "Test Article"
        assert len(data['authors']) == 1
        assert data['authors'][0]['full_name'] == "John Doe"
        assert len(data['identifiers']) == 1
        assert data['identifiers'][0]['identifier_value'] == "10.1000/test"
    
    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            'article': {
                'title': 'Test Article',
                'primary_doi': '10.1000/test',
                'publication_year': 2023
            },
            'authors': [
                {'full_name': 'John Doe', 'author_order': 1}
            ],
            'venue': {
                'venue_name': 'Nature',
                'venue_type': 'journal'
            },
            'identifiers': [
                {
                    'identifier_type': 'doi',
                    'identifier_value': '10.1000/test',
                    'is_primary': True
                }
            ],
            'categories': [
                {
                    'category_name': 'Machine Learning',
                    'category_type': 'field_of_study'
                }
            ],
            'source_specific': {'source': 'test'}
        }
        
        literature = LiteratureSchema.from_dict(data)
        
        assert literature.article.title == "Test Article"
        assert literature.article.primary_doi == "10.1000/test"
        assert literature.article.publication_year == 2023
        assert len(literature.authors) == 1
        assert literature.authors[0].full_name == "John Doe"
        assert literature.venue.venue_name == "Nature"
        assert literature.venue.venue_type == VenueType.JOURNAL
        assert len(literature.identifiers) == 1
        assert literature.identifiers[0].identifier_type == IdentifierType.DOI
        assert len(literature.categories) == 1
        assert literature.categories[0].category_type == CategoryType.FIELD_OF_STUDY
    
    def test_string_representations(self):
        """Test string representations."""
        literature = LiteratureSchema()
        literature.article.title = "A Very Long Title That Should Be Truncated When Displayed"
        literature.add_author("John Doe")
        literature.add_identifier(IdentifierType.DOI, "10.1000/test")
        literature.source_specific = {'source': 'test'}
        
        str_repr = str(literature)
        assert "A Very Long Title That Should Be Truncated When" in str_repr
        assert "authors=1" in str_repr
        
        repr_str = repr(literature)
        assert "A Very Long Title That Should Be Truncated When Displayed" in repr_str
        assert "authors=1" in repr_str
        assert "identifiers=1" in repr_str
        assert "source='test'" in repr_str