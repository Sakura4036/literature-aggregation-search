"""
Integration tests for literature schema classes with existing systems.
"""

import pytest
import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.models import LiteratureSchema, IdentifierType, VenueType
from src.search.response_formatter import ResponseFormatter


class TestSchemaIntegration:
    """Test integration between schema classes and existing systems."""
    
    def test_schema_with_pubmed_formatter(self):
        """Test that schema works with PubMed response formatter output."""
        # Sample PubMed data (similar to what pubmed_search.py returns)
        pubmed_data = {
            'pmid': '12345678',
            'title': 'Test Article Title',
            'abstract': 'This is a test abstract for the article.',
            'authors': ['John Doe', 'Jane Smith'],
            'journal': 'Nature',
            'issn': '0028-0836',
            'volume': '123',
            'issue': '4567',
            'eissn': '1476-4687',
            'doi': '10.1038/test123',
            'published_date': '2023-06-15',
            'year': 2023
        }
        
        # Format using existing formatter
        formatted_data = ResponseFormatter.format_pubmed(pubmed_data)
        
        # Create schema from formatted data
        literature = LiteratureSchema.from_dict(formatted_data)
        
        # Verify the data was correctly converted
        assert literature.article.title == 'Test Article Title'
        assert literature.article.abstract == 'This is a test abstract for the article.'
        assert literature.article.primary_doi == '10.1038/test123'
        assert literature.article.publication_year == 2023
        assert literature.article.publication_date == '2023-06-15'
        
        assert len(literature.authors) == 2
        assert literature.authors[0].full_name == 'John Doe'
        assert literature.authors[1].full_name == 'Jane Smith'
        
        assert literature.venue.venue_name == 'Nature'
        assert literature.venue.venue_type == VenueType.JOURNAL
        assert literature.venue.issn_print == '0028-0836'
        assert literature.venue.issn_electronic == '1476-4687'
        
        # Check identifiers
        doi_identifier = None
        pmid_identifier = None
        for identifier in literature.identifiers:
            if identifier.identifier_type == IdentifierType.DOI:
                doi_identifier = identifier
            elif identifier.identifier_type == IdentifierType.PMID:
                pmid_identifier = identifier
        
        assert doi_identifier is not None
        assert doi_identifier.identifier_value == '10.1038/test123'
        assert doi_identifier.is_primary is True
        
        assert pmid_identifier is not None
        assert pmid_identifier.identifier_value == '12345678'
        assert pmid_identifier.is_primary is False
        
        # Validate the schema
        is_valid, errors = literature.validate()
        assert is_valid is True
        assert len(errors) == 0
    
    def test_schema_with_arxiv_formatter(self):
        """Test that schema works with ArXiv response formatter output."""
        # Sample ArXiv data
        arxiv_data = {
            'title': 'Machine Learning in Quantum Computing',
            'abstract': 'This paper explores the intersection of ML and quantum computing.',
            'authors': ['Alice Johnson', 'Bob Wilson'],
            'journal': 'arXiv preprint',
            'doi': '10.48550/arxiv.2301.00001',
            'arxiv_id': '2301.00001',
            'published_date': '2023-01-01',
            'year': 2023,
            'pdf_url': 'https://arxiv.org/pdf/2301.00001.pdf',
            'arxiv': {'id': '2301.00001', 'category': 'quant-ph'}
        }
        
        # Format using existing formatter
        formatted_data = ResponseFormatter.format_arxiv(arxiv_data)
        
        # Create schema from formatted data
        literature = LiteratureSchema.from_dict(formatted_data)
        
        # Verify the data
        assert literature.article.title == 'Machine Learning in Quantum Computing'
        assert literature.article.is_open_access is True
        assert literature.article.open_access_url == 'https://arxiv.org/pdf/2301.00001.pdf'
        
        assert literature.venue.venue_type == VenueType.PREPRINT_SERVER
        
        # Check for ArXiv ID
        arxiv_id = literature.get_arxiv_id()
        assert arxiv_id == '2301.00001'
        
        # Validate
        is_valid, errors = literature.validate()
        assert is_valid is True
    
    def test_schema_with_semantic_scholar_formatter(self):
        """Test that schema works with Semantic Scholar response formatter output."""
        # Sample Semantic Scholar data
        semantic_data = {
            'title': 'Deep Learning Applications',
            'abstract': 'A comprehensive review of deep learning applications.',
            'authors': ['Dr. Smith', 'Prof. Johnson'],
            'journal': 'Journal of AI Research',
            'venue': 'JAIR',
            'doi': '10.1613/jair.1.12345',
            'pmid': '87654321',
            'paperId': 'abc123def456',
            'year': 2023,
            'citation_count': 150,
            'references_count': 75,
            'isOpenAccess': True,
            'openAccessPdf': 'https://example.com/paper.pdf',
            'types': ['JournalArticle', 'Review'],
            'semantic_scholar': {'paperId': 'abc123def456', 'fieldsOfStudy': ['Computer Science']}
        }
        
        # Format using existing formatter
        formatted_data = ResponseFormatter.format_semantic_scholar(semantic_data)
        
        # Create schema from formatted data
        literature = LiteratureSchema.from_dict(formatted_data)
        
        # Verify the data
        assert literature.article.citation_count == 150
        assert literature.article.reference_count == 75
        assert literature.article.is_open_access is True
        
        # Check Semantic Scholar ID
        ss_id = literature.get_identifier(IdentifierType.SEMANTIC_SCHOLAR_ID)
        assert ss_id == 'abc123def456'
        
        # Check publication types
        assert len(literature.publication_types) == 2
        type_names = [pt.type_name for pt in literature.publication_types]
        assert 'JournalArticle' in type_names
        assert 'Review' in type_names
        
        # Validate
        is_valid, errors = literature.validate()
        assert is_valid is True
    
    def test_schema_roundtrip_conversion(self):
        """Test that schema can be converted to dict and back without data loss."""
        # Create a comprehensive literature record
        literature = LiteratureSchema()
        
        # Set all types of data
        literature.article.title = "Comprehensive Test Article"
        literature.article.primary_doi = "10.1000/test"
        literature.article.publication_year = 2023
        literature.article.citation_count = 42
        
        literature.add_author("John Doe", orcid="0000-0000-0000-0000")
        literature.add_author("Jane Smith", is_corresponding=True)
        
        literature.venue.venue_name = "Test Journal"
        literature.venue.venue_type = VenueType.JOURNAL
        
        literature.add_identifier(IdentifierType.DOI, "10.1000/test", is_primary=True)
        literature.add_identifier(IdentifierType.PMID, "12345678")
        
        literature.add_category("Machine Learning")
        
        literature.source_specific = {'source': 'test', 'version': '1.0'}
        
        # Convert to dict and back
        data = literature.to_dict()
        restored = LiteratureSchema.from_dict(data)
        
        # Verify all data is preserved
        assert restored.article.title == literature.article.title
        assert restored.article.primary_doi == literature.article.primary_doi
        assert restored.article.publication_year == literature.article.publication_year
        assert restored.article.citation_count == literature.article.citation_count
        
        assert len(restored.authors) == len(literature.authors)
        assert restored.authors[0].full_name == literature.authors[0].full_name
        assert restored.authors[0].orcid == literature.authors[0].orcid
        assert restored.authors[1].is_corresponding == literature.authors[1].is_corresponding
        
        assert restored.venue.venue_name == literature.venue.venue_name
        assert restored.venue.venue_type == literature.venue.venue_type
        
        assert len(restored.identifiers) == len(literature.identifiers)
        assert restored.get_doi() == literature.get_doi()
        assert restored.get_pmid() == literature.get_pmid()
        
        assert len(restored.categories) == len(literature.categories)
        assert restored.categories[0].category_name == literature.categories[0].category_name
        
        assert restored.source_specific == literature.source_specific
        
        # Both should validate successfully
        is_valid_original, _ = literature.validate()
        is_valid_restored, _ = restored.validate()
        assert is_valid_original is True
        assert is_valid_restored is True
    
    def test_schema_with_missing_optional_fields(self):
        """Test that schema handles missing optional fields gracefully."""
        # Minimal data with only required fields
        minimal_data = {
            'article': {
                'title': 'Minimal Article'
            },
            'authors': [],
            'venue': {},
            'identifiers': [],
            'source_specific': {'source': 'test'}
        }
        
        # Should create successfully
        literature = LiteratureSchema.from_dict(minimal_data)
        
        # Should validate (title is present)
        is_valid, errors = literature.validate()
        assert is_valid is True
        
        # Optional fields should have default values
        assert literature.article.primary_doi is None
        assert literature.article.publication_year is None
        assert literature.article.citation_count == 0
        assert literature.article.is_open_access is False
        
        assert len(literature.authors) == 0
        assert len(literature.identifiers) == 0
        
        assert literature.venue.venue_name == ""
        assert literature.venue.venue_type == VenueType.OTHER