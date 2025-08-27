"""
Unit tests for refactored PubmedSearchAPI.

This module contains comprehensive tests for the PubmedSearchAPI class,
including search functionality, parameter validation, result formatting,
and integration with the BaseSearchEngine architecture.
"""

import json
import os
from unittest.mock import patch

import pytest
from src.search.engine import PubmedSearchAPI

from src.models.enums import IdentifierType, VenueType
from src.search.engine.base_engine import BaseSearchEngine, NetworkError


class TestPubmedSearchAPI:
    """Test cases for PubmedSearchAPI class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = PubmedSearchAPI()
        
        # Load real template data
        template_path = os.path.join(os.path.dirname(__file__), '..', '..', 'templates', 'temp_pubmed_parsed_article.json')
        with open(template_path, 'r', encoding='utf-8') as f:
            self.template_data = json.load(f)
        
        # Use first item from template as test data
        self.sample_result = self.template_data[0]
        
        # Convert template data to expected parsed format
        self.expected_parsed_result = {
            'pmid': self.sample_result['pmid'],
            'title': self.sample_result['title'],
            'abstract': self.sample_result['abstract']['text'],
            'authors': [f"{author['fore_name']} {author['last_name']}" for author in self.sample_result['authors']],
            'journal': self.sample_result['journal_title'],
            'issn': self.sample_result['issn_print'],
            'eissn': self.sample_result['issn_electronic'],
            'volume': self.sample_result['volume'],
            'issue': self.sample_result['issue'],
            'doi': self.sample_result['identifiers']['doi'],
            'published_date': self.sample_result['electronic_pub_date']['iso_date'],
            'year': int(self.sample_result['electronic_pub_date']['year'])
        }
    
    def test_inheritance_from_base_engine(self):
        """Test that PubmedSearchAPI properly inherits from BaseSearchEngine."""
        assert isinstance(self.api, BaseSearchEngine)
        assert hasattr(self.api, 'search')
        assert hasattr(self.api, '_search')
        assert hasattr(self.api, '_response_format')
        assert hasattr(self.api, 'get_source_name')
    
    def test_initialization(self):
        """Test PubmedSearchAPI initialization."""
        api = PubmedSearchAPI()
        
        assert api.source_name == 'pubmed'
        assert api.default_results == 50
        assert hasattr(api, 'pubmed_search_url')
        assert hasattr(api, 'pubmed_fetch_url')
        assert api.pubmed_search_url == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
        assert api.pubmed_fetch_url == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?"
    
    def test_get_source_name(self):
        """Test get_source_name method."""
        assert self.api.get_source_name() == 'pubmed'
    
    @patch('src.search.pubmed_search.PubmedSearchAPI.query')
    def test_search_method_basic(self, mock_query):
        """Test basic _search method functionality."""
        # Setup mocks
        mock_query.return_value = ([self.expected_parsed_result], {"count": 1})
        
        # Execute search
        results, metadata = self.api._search("alkaline phosphatase", num_results=10)
        
        # Verify results
        assert len(results) == 1
        assert results[0] == self.expected_parsed_result
        
        # Verify metadata
        assert metadata["count"] == 1
        
        # Verify method calls
        mock_query.assert_called_once_with(
            query="alkaline phosphatase",
            year="",
            field="",
            sort="relevance",
            num_results=10
        )
    
    @patch('src.search.pubmed_search.PubmedSearchAPI.query')
    def test_search_with_parameters(self, mock_query):
        """Test _search method with various parameters."""
        # Setup mocks
        mock_query.return_value = ([self.expected_parsed_result], {"count": 1})
        
        # Execute search with parameters
        results, metadata = self.api._search(
            "test query",
            year="2020-2023",
            field="Title",
            sort="pub_date",
            num_results=20
        )
        
        # Verify query was called with correct parameters
        mock_query.assert_called_once_with(
            query="test query",
            year="2020-2023",
            field="Title",
            sort="pub_date",
            num_results=20
        )
    
    @patch('src.search.pubmed_search.PubmedSearchAPI.query')
    def test_search_network_error_handling(self, mock_query):
        """Test that network errors are properly handled."""
        # Setup mock to raise exception
        mock_query.side_effect = Exception("Network connection failed")
        
        # Verify NetworkError is raised
        with pytest.raises(NetworkError) as exc_info:
            self.api._search("test query")
        
        assert "PubMed search failed" in str(exc_info.value)
    
    def test_response_format_basic(self):
        """Test basic _response_format functionality."""
        # Test data using template
        raw_results = [self.expected_parsed_result]
        
        # Execute formatting
        formatted_results = self.api._response_format(raw_results)
        
        # Verify results structure
        assert len(formatted_results) == 1
        result = formatted_results[0]
        
        # Verify it's a valid dictionary representation of LiteratureSchema
        assert 'article' in result
        assert 'authors' in result
        assert 'venue' in result
        assert 'identifiers' in result
        assert 'publication' in result
        assert 'source_specific' in result
        
        # Verify article information using template data
        article = result['article']
        assert article['title'] == self.sample_result['title']
        assert article['abstract'] == self.sample_result['abstract']['text']
        assert article['primary_doi'] == self.sample_result['identifiers']['doi']
        assert article['publication_year'] == int(self.sample_result['electronic_pub_date']['year'])
        assert article['is_open_access'] is False  # PubMed doesn't provide this directly
        
        # Verify authors using template data
        authors = result['authors']
        expected_authors = [f"{author['fore_name']} {author['last_name']}" for author in self.sample_result['authors']]
        assert len(authors) == len(expected_authors)
        for i, expected_author in enumerate(expected_authors):
            assert authors[i]['full_name'] == expected_author
            assert authors[i]['author_order'] == i + 1
        
        # Verify venue
        venue = result['venue']
        assert venue['venue_name'] == self.sample_result['journal_title']
        # Handle enum comparison
        assert (venue['venue_type'] == VenueType.JOURNAL or 
               venue['venue_type'] == VenueType.JOURNAL.value)
        # Handle empty string vs None for ISSN
        expected_issn_print = self.sample_result['issn_print'] or None
        expected_issn_electronic = self.sample_result['issn_electronic'] or None
        assert venue['issn_print'] == expected_issn_print
        assert venue['issn_electronic'] == expected_issn_electronic
        
        # Verify publication details
        publication = result['publication']
        assert publication['volume'] == self.sample_result['volume']
        assert publication['issue'] == self.sample_result['issue']
        
        # Verify identifiers
        identifiers = result['identifiers']
        assert len(identifiers) >= 2  # DOI and PMID
        
        # Find DOI identifier - handle enum comparison
        doi_identifier = next((id for id in identifiers if 
                              id['identifier_type'] == IdentifierType.DOI or 
                              id['identifier_type'] == IdentifierType.DOI.value), None)
        assert doi_identifier is not None
        assert doi_identifier['identifier_value'] == self.sample_result['identifiers']['doi']
        assert doi_identifier['is_primary'] is True
        
        # Find PMID identifier - handle enum comparison
        pmid_identifier = next((id for id in identifiers if 
                              id['identifier_type'] == IdentifierType.PMID or 
                              id['identifier_type'] == IdentifierType.PMID.value), None)
        assert pmid_identifier is not None
        assert pmid_identifier['identifier_value'] == self.sample_result['pmid']
        
        # Verify source specific data
        source_specific = result['source_specific']
        assert source_specific['source'] == 'pubmed'
        assert 'raw_data' in source_specific
    
    def test_response_format_no_doi(self):
        """Test _response_format when DOI is not available."""
        # Test data without DOI
        raw_result = self.expected_parsed_result.copy()
        raw_result['doi'] = ""
        
        formatted_results = self.api._response_format([raw_result])
        result = formatted_results[0]
        
        # Verify PMID becomes primary when no DOI
        identifiers = result['identifiers']
        pmid_identifier = next((id for id in identifiers if 
                              id['identifier_type'] == IdentifierType.PMID or 
                              id['identifier_type'] == IdentifierType.PMID.value), None)
        assert pmid_identifier is not None
        assert pmid_identifier['is_primary'] is True
    
    def test_response_format_missing_fields(self):
        """Test _response_format with missing optional fields."""
        # Test data with minimal fields
        minimal_result = {
            'pmid': '12345',
            'title': 'Minimal Paper',
            'authors': ['Single Author'],
            'journal': 'Test Journal',
            'year': 2023
        }
        
        formatted_results = self.api._response_format([minimal_result])
        result = formatted_results[0]
        
        # Verify it still creates a valid structure
        assert result['article']['title'] == 'Minimal Paper'
        assert len(result['authors']) == 1
        assert result['authors'][0]['full_name'] == 'Single Author'
        assert result['venue']['venue_name'] == 'Test Journal'
    
    def test_response_format_error_handling(self):
        """Test _response_format error handling for malformed data."""
        # Test with malformed data that should be skipped due to missing title
        malformed_result = {'invalid': 'data'}
        
        # Should not raise exception, but log warning and continue
        with patch.object(self.api.logger, 'warning') as mock_warning:
            formatted_results = self.api._response_format([malformed_result])
            
            # Should create result but with validation warnings
            assert len(formatted_results) == 1
            mock_warning.assert_called()
            
            # Verify warning message mentions validation
            warning_calls = [call.args[0] for call in mock_warning.call_args_list]
            assert any("Schema validation failed" in call for call in warning_calls)
    
    def test_validate_params_basic(self):
        """Test basic parameter validation."""
        # Valid parameters
        assert self.api.validate_params("test query") is True
        assert self.api.validate_params("test query", num_results=100) is True
        assert self.api.validate_params("test query", field="Title") is True
        assert self.api.validate_params("test query", sort="relevance") is True
    
    def test_validate_params_pubmed_specific(self):
        """Test PubMed-specific parameter validation."""
        # Test valid sort values
        valid_sorts = ['relevance', 'pub_date', 'Author', 'JournalName']
        for sort_val in valid_sorts:
            assert self.api.validate_params("test", sort=sort_val) is True
        
        # Test invalid sort
        assert self.api.validate_params("test", sort="invalid") is False
        
        # Test field validation (should allow various formats)
        assert self.api.validate_params("test", field="Title") is True
        assert self.api.validate_params("test", field="[Title]") is True
        assert self.api.validate_params("test", field="") is True
    
    def test_validate_params_inherits_base_validation(self):
        """Test that PubMed validation includes base class validation."""
        # These should fail due to base class validation
        assert self.api.validate_params("") is False
        assert self.api.validate_params("test", num_results=0) is False
        assert self.api.validate_params("test", num_results=-1) is False
    
    @patch('src.search.pubmed_search.PubmedSearchAPI._search')
    @patch('src.search.pubmed_search.PubmedSearchAPI._response_format')
    def test_search_integration(self, mock_format, mock_search):
        """Test integration of search method with base class."""
        # Setup mocks
        raw_results = [self.expected_parsed_result]
        metadata = {'count': 1, 'query': 'test'}
        formatted_results = [{'formatted': 'result'}]
        
        mock_search.return_value = (raw_results, metadata)
        mock_format.return_value = formatted_results
        
        # Execute search
        results, final_metadata = self.api.search("test query", num_results=10)
        
        # Verify results
        assert results == formatted_results
        
        # Verify metadata includes base class additions
        assert final_metadata['source'] == 'pubmed'
        assert final_metadata['formatted_count'] == 1
        assert 'search_duration_seconds' in final_metadata
        assert 'timestamp' in final_metadata
    
    def test_search_legacy_compatibility(self):
        """Test legacy search method for backward compatibility."""
        with patch.object(self.api, 'search') as mock_search:
            # Setup mock
            formatted_results = [{'source_specific': {'raw_data': self.expected_parsed_result}}]
            metadata = {'test': 'metadata'}
            mock_search.return_value = (formatted_results, metadata)
            
            # Execute legacy search
            results, returned_metadata = self.api.search_legacy(
                query="test query",
                year="2023",
                field="Title",
                sort="pub_date",
                num_results=10
            )
            
            # Verify legacy format is returned
            assert len(results) == 1
            assert results[0] == self.expected_parsed_result
            assert returned_metadata == metadata
            
            # Verify new search method was called with correct parameters
            mock_search.assert_called_once_with(
                query="test query",
                year="2023",
                field="Title",
                sort="pub_date",
                num_results=10
            )
    
    def test_schema_validation_in_format(self):
        """Test that schema validation is performed during formatting."""
        # Test with data that should trigger validation warnings
        result_with_warnings = self.expected_parsed_result.copy()
        result_with_warnings['year'] = 3000  # Invalid year should trigger validation warning
        
        with patch.object(self.api.logger, 'warning') as mock_warning:
            formatted_results = self.api._response_format([result_with_warnings])
            
            # Should still return result but log warning
            assert len(formatted_results) == 1
            mock_warning.assert_called()
            
            # Verify warning message mentions validation
            warning_calls = [call.args[0] for call in mock_warning.call_args_list]
            assert any("Schema validation failed" in call for call in warning_calls)


class TestPubmedSearchAPIEdgeCases:
    """Test edge cases and error conditions for PubmedSearchAPI."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = PubmedSearchAPI()
    
    def test_empty_results_handling(self):
        """Test handling of empty search results."""
        formatted_results = self.api._response_format([])
        assert formatted_results == []
    
    def test_malformed_author_data(self):
        """Test handling of malformed author data."""
        result_with_bad_authors = {
            'pmid': '12345',
            'title': 'Test Paper',
            'authors': [None, '', '   ', 'Valid Author'],  # Mix of invalid and valid
            'journal': 'Test Journal',
            'year': 2023
        }
        
        formatted_results = self.api._response_format([result_with_bad_authors])
        result = formatted_results[0]
        
        # Should only include valid author
        authors = result['authors']
        assert len(authors) == 1
        assert authors[0]['full_name'] == 'Valid Author'
    
    def test_missing_pmid(self):
        """Test handling when PMID is missing."""
        result_without_pmid = {
            'title': 'Test Paper',
            'authors': ['Author'],
            'journal': 'Test Journal',
            'year': 2023
        }
        
        formatted_results = self.api._response_format([result_without_pmid])
        result = formatted_results[0]
        
        # Should still create valid result
        assert result['article']['title'] == 'Test Paper'
        
        # Should not have PMID identifier
        identifiers = result['identifiers']
        pmid_ids = [id for id in identifiers if 
                   id['identifier_type'] == IdentifierType.PMID or 
                   id['identifier_type'] == IdentifierType.PMID.value]
        assert len(pmid_ids) == 0


if __name__ == "__main__":
    pytest.main([__file__])