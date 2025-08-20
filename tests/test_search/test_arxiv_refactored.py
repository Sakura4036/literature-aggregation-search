"""
Unit tests for refactored ArxivSearchAPI.

This module contains comprehensive tests for the ArxivSearchAPI class,
including search functionality, parameter validation, result formatting,
and integration with the BaseSearchEngine architecture.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date
from typing import List, Dict

from src.search.arxiv_search import ArxivSearchAPI, ArxivClient
from src.search.base_engine import BaseSearchEngine, NetworkError, FormatError, ParameterValidationError
from src.models.schemas import LiteratureSchema, ArticleSchema, AuthorSchema, VenueSchema, IdentifierSchema, CategorySchema
from src.models.enums import IdentifierType, VenueType, CategoryType


class TestArxivSearchAPI:
    """Test cases for ArxivSearchAPI class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = ArxivSearchAPI()
        
        # Mock ArXiv result object
        self.mock_arxiv_result = Mock()
        self.mock_arxiv_result.title = "Test ArXiv Paper"
        self.mock_arxiv_result.summary = "This is a test abstract"
        self.mock_arxiv_result.authors = [Mock(name="John Doe"), Mock(name="Jane Smith")]
        self.mock_arxiv_result.doi = "10.1234/test.doi"
        self.mock_arxiv_result.get_short_id.return_value = "2301.12345"
        self.mock_arxiv_result.published = datetime(2023, 1, 15)
        self.mock_arxiv_result.updated = datetime(2023, 1, 16)
        self.mock_arxiv_result.journal_ref = "Test Journal"
        self.mock_arxiv_result.entry_id = "http://arxiv.org/abs/2301.12345"
        self.mock_arxiv_result.categories = ["cs.AI", "cs.LG"]
        self.mock_arxiv_result.pdf_url = "http://arxiv.org/pdf/2301.12345.pdf"
        
        # Expected parsed result
        self.expected_parsed_result = {
            'title': 'Test ArXiv Paper',
            'abstract': 'This is a test abstract',
            'authors': ['John Doe', 'Jane Smith'],
            'doi': '10.1234/test.doi',
            'arxiv_id': '2301.12345',
            'year': 2023,
            'published_date': '2023-01-15',
            'updated_date': '2023-01-16',
            'journal': 'Test Journal',
            'url': 'http://arxiv.org/abs/2301.12345',
            'categories': ['cs.AI', 'cs.LG'],
            'pdf_url': 'http://arxiv.org/pdf/2301.12345.pdf',
            'arxiv': {}  # This would contain the full result_to_dict output
        }
    
    def test_inheritance_from_base_engine(self):
        """Test that ArxivSearchAPI properly inherits from BaseSearchEngine."""
        assert isinstance(self.api, BaseSearchEngine)
        assert hasattr(self.api, 'search')
        assert hasattr(self.api, '_search')
        assert hasattr(self.api, '_response_format')
        assert hasattr(self.api, 'get_source_name')
    
    def test_initialization(self):
        """Test ArxivSearchAPI initialization."""
        api = ArxivSearchAPI()
        
        assert api.source_name == 'arxiv'
        assert api.max_results_limit == 2000  # ArXiv specific limit
        assert api.default_results == 50
        assert hasattr(api, 'client')
        assert isinstance(api.client, ArxivClient)
    
    def test_get_source_name(self):
        """Test get_source_name method."""
        assert self.api.get_source_name() == 'arxiv'
    
    @patch('src.search.arxiv_search.ArxivSearchAPI._query')
    @patch('src.search.arxiv_search.ArxivSearchAPI._parse')
    def test_search_method_basic(self, mock_parse, mock_query):
        """Test basic _search method functionality."""
        # Setup mocks
        mock_query.return_value = [self.mock_arxiv_result]
        mock_parse.return_value = [self.expected_parsed_result]
        
        # Execute search
        results, metadata = self.api._search("machine learning", num_results=10)
        
        # Verify results
        assert len(results) == 1
        assert results[0] == self.expected_parsed_result
        
        # Verify metadata
        assert 'query' in metadata
        assert 'original_query' in metadata
        assert metadata['original_query'] == "machine learning"
        assert metadata['requested_results'] == 10
        
        # Verify method calls
        mock_query.assert_called_once()
        mock_parse.assert_called_once_with([self.mock_arxiv_result])
    
    @patch('src.search.arxiv_search.year_split')
    @patch('src.search.arxiv_search.ArxivSearchAPI._query')
    @patch('src.search.arxiv_search.ArxivSearchAPI._parse')
    def test_search_with_year_filter(self, mock_parse, mock_query, mock_year_split):
        """Test _search method with year filtering."""
        # Setup mocks
        mock_year_split.return_value = (2020, 2022)
        mock_query.return_value = [self.mock_arxiv_result]
        mock_parse.return_value = [self.expected_parsed_result]
        
        # Execute search with year filter
        results, metadata = self.api._search("test query", year="2020-2022")
        
        # Verify year_split was called
        mock_year_split.assert_called_once_with("2020-2022")
        
        # Verify query was modified to include year filter
        call_args = mock_query.call_args[0]
        search_query = call_args[0]
        assert "submittedDate:" in search_query
        assert "2020010101600 TO 202301010600" in search_query
    
    @patch('src.search.arxiv_search.ArxivSearchAPI._query')
    def test_search_network_error_handling(self, mock_query):
        """Test that network errors are properly handled."""
        # Setup mock to raise exception
        mock_query.side_effect = Exception("Network connection failed")
        
        # Verify NetworkError is raised
        with pytest.raises(NetworkError) as exc_info:
            self.api._search("test query")
        
        assert "ArXiv search failed" in str(exc_info.value)
    
    def test_response_format_basic(self):
        """Test basic _response_format functionality."""
        # Test data
        raw_results = [self.expected_parsed_result]
        
        # Execute formatting
        formatted_results = self.api._response_format(raw_results, 'arxiv')
        
        # Verify results structure
        assert len(formatted_results) == 1
        result = formatted_results[0]
        
        # Verify it's a valid dictionary representation of LiteratureSchema
        assert 'article' in result
        assert 'authors' in result
        assert 'venue' in result
        assert 'identifiers' in result
        assert 'categories' in result
        assert 'source_specific' in result
        
        # Verify article information
        article = result['article']
        assert article['title'] == 'Test ArXiv Paper'
        assert article['abstract'] == 'This is a test abstract'
        assert article['primary_doi'] == '10.1234/test.doi'
        assert article['publication_year'] == 2023
        assert article['is_open_access'] is True
        
        # Verify authors
        authors = result['authors']
        assert len(authors) == 2
        assert authors[0]['full_name'] == 'John Doe'
        assert authors[0]['author_order'] == 1
        assert authors[1]['full_name'] == 'Jane Smith'
        assert authors[1]['author_order'] == 2
        
        # Verify venue
        venue = result['venue']
        assert venue['venue_name'] == 'Test Journal'
        assert venue['venue_type'] == VenueType.PREPRINT_SERVER
        
        # Verify identifiers
        identifiers = result['identifiers']
        assert len(identifiers) >= 2  # DOI and ArXiv ID
        
        # Find DOI identifier
        doi_identifier = next((id for id in identifiers if id['identifier_type'] == IdentifierType.DOI), None)
        assert doi_identifier is not None
        assert doi_identifier['identifier_value'] == '10.1234/test.doi'
        assert doi_identifier['is_primary'] is True
        
        # Find ArXiv ID identifier
        arxiv_identifier = next((id for id in identifiers if id['identifier_type'] == IdentifierType.ARXIV_ID), None)
        assert arxiv_identifier is not None
        assert arxiv_identifier['identifier_value'] == '2301.12345'
        
        # Verify categories
        categories = result['categories']
        assert len(categories) == 2
        assert categories[0]['category_name'] == 'cs.AI'
        assert categories[0]['category_type'] == CategoryType.ARXIV_CATEGORY
        
        # Verify source specific data
        source_specific = result['source_specific']
        assert source_specific['source'] == 'arxiv'
        assert 'raw_data' in source_specific
        assert 'pdf_url' in source_specific
    
    def test_response_format_no_doi(self):
        """Test _response_format when DOI is not available."""
        # Test data without DOI
        raw_result = self.expected_parsed_result.copy()
        raw_result['doi'] = None
        
        formatted_results = self.api._response_format([raw_result], 'arxiv')
        result = formatted_results[0]
        
        # Verify ArXiv ID becomes primary when no DOI
        identifiers = result['identifiers']
        arxiv_identifier = next((id for id in identifiers if id['identifier_type'] == IdentifierType.ARXIV_ID), None)
        assert arxiv_identifier is not None
        assert arxiv_identifier['is_primary'] is True
    
    def test_response_format_missing_fields(self):
        """Test _response_format with missing optional fields."""
        # Test data with minimal fields
        minimal_result = {
            'title': 'Minimal Paper',
            'authors': ['Single Author'],
            'arxiv_id': '2301.99999',
            'year': 2023,
            'categories': []
        }
        
        formatted_results = self.api._response_format([minimal_result], 'arxiv')
        result = formatted_results[0]
        
        # Verify it still creates a valid structure
        assert result['article']['title'] == 'Minimal Paper'
        assert len(result['authors']) == 1
        assert result['authors'][0]['full_name'] == 'Single Author'
        assert len(result['categories']) == 0
        
        # Verify venue defaults
        venue = result['venue']
        assert venue['venue_name'] == 'arXiv'  # Default when no journal
        assert venue['venue_type'] == VenueType.PREPRINT_SERVER
    
    def test_response_format_error_handling(self):
        """Test _response_format error handling for malformed data."""
        # Test with malformed data
        malformed_result = {'invalid': 'data'}
        
        # Should not raise exception, but log warning and continue
        formatted_results = self.api._response_format([malformed_result], 'arxiv')
        
        # Should skip malformed data and return empty list
        assert len(formatted_results) == 0
    
    def test_validate_params_basic(self):
        """Test basic parameter validation."""
        # Valid parameters
        assert self.api.validate_params("test query") is True
        assert self.api.validate_params("test query", num_results=100) is True
        assert self.api.validate_params("test query", sort_by="relevance") is True
        assert self.api.validate_params("test query", sort_order="descending") is True
    
    def test_validate_params_arxiv_specific(self):
        """Test ArXiv-specific parameter validation."""
        # Test ArXiv result limit
        assert self.api.validate_params("test", num_results=2000) is True
        assert self.api.validate_params("test", num_results=2001) is False
        
        # Test valid sort_by values
        valid_sort_by = ['relevance', 'lastUpdatedDate', 'submittedDate']
        for sort_by in valid_sort_by:
            assert self.api.validate_params("test", sort_by=sort_by) is True
        
        # Test invalid sort_by
        assert self.api.validate_params("test", sort_by="invalid") is False
        
        # Test valid sort_order values
        valid_sort_order = ['ascending', 'descending']
        for sort_order in valid_sort_order:
            assert self.api.validate_params("test", sort_order=sort_order) is True
        
        # Test invalid sort_order
        assert self.api.validate_params("test", sort_order="invalid") is False
        
        # Test id_list validation
        assert self.api.validate_params("test", id_list=[]) is True
        assert self.api.validate_params("test", id_list=["2301.12345"]) is True
        assert self.api.validate_params("test", id_list="not_a_list") is False
    
    def test_validate_params_inherits_base_validation(self):
        """Test that ArXiv validation includes base class validation."""
        # These should fail due to base class validation
        assert self.api.validate_params("") is False
        assert self.api.validate_params("test", num_results=0) is False
        assert self.api.validate_params("test", num_results=-1) is False
        assert self.api.validate_params("test", year="invalid") is False
    
    @patch('src.search.arxiv_search.ArxivSearchAPI._search')
    @patch('src.search.arxiv_search.ArxivSearchAPI._response_format')
    def test_search_integration(self, mock_format, mock_search):
        """Test integration of search method with base class."""
        # Setup mocks
        raw_results = [self.expected_parsed_result]
        metadata = {'query': 'test', 'raw_count': 1}
        formatted_results = [{'formatted': 'result'}]
        
        mock_search.return_value = (raw_results, metadata)
        mock_format.return_value = formatted_results
        
        # Execute search
        results, final_metadata = self.api.search("test query", num_results=10)
        
        # Verify results
        assert results == formatted_results
        
        # Verify metadata includes base class additions
        assert final_metadata['source'] == 'arxiv'
        assert final_metadata['formatted_count'] == 1
        assert final_metadata['raw_count'] == 1
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
                num_results=10,
                sort_by="relevance",
                year="2023"
            )
            
            # Verify legacy format is returned
            assert len(results) == 1
            assert results[0] == self.expected_parsed_result
            assert returned_metadata == metadata
            
            # Verify new search method was called with correct parameters
            mock_search.assert_called_once_with(
                "test query",
                num_results=10,
                id_list=[],
                sort_by="relevance",
                sort_order="descending",
                year="2023"
            )
    
    def test_search_legacy_with_none_query(self):
        """Test legacy search with None query."""
        with patch.object(self.api, 'search') as mock_search:
            mock_search.return_value = ([], {})
            
            # Execute with None query
            self.api.search_legacy(query=None)
            
            # Verify empty string was passed to new search
            mock_search.assert_called_once()
            args, kwargs = mock_search.call_args
            assert args[0] == ""  # Empty string instead of None
    
    def test_search_with_zero_results(self):
        """Test search behavior when num_results is 0."""
        results, metadata = self.api._search("test", num_results=0)
        
        assert results == []
        assert metadata['query'] == "test"
    
    @patch('src.search.arxiv_search.ArxivSearchAPI._query')
    @patch('src.search.arxiv_search.ArxivSearchAPI._parse')
    def test_search_with_all_parameters(self, mock_parse, mock_query):
        """Test search with all possible parameters."""
        # Setup mocks
        mock_query.return_value = [self.mock_arxiv_result]
        mock_parse.return_value = [self.expected_parsed_result]
        
        # Execute search with all parameters
        results, metadata = self.api._search(
            "machine learning",
            num_results=50,
            id_list=["2301.12345"],
            sort_by="lastUpdatedDate",
            sort_order="ascending",
            year="2023"
        )
        
        # Verify all parameters are in metadata
        assert metadata['requested_results'] == 50
        assert metadata['sort_by'] == "lastUpdatedDate"
        assert metadata['sort_order'] == "ascending"
        assert metadata['year_filter'] == "2023"
        
        # Verify query method was called with correct parameters
        mock_query.assert_called_once()
        call_args = mock_query.call_args
        assert call_args[1]['max_results'] == 50
        assert call_args[1]['sort_by'] == "lastUpdatedDate"
        assert call_args[1]['sort_order'] == "ascending"
    
    def test_schema_validation_in_format(self):
        """Test that schema validation is performed during formatting."""
        # Test with invalid data that should trigger validation warnings but not be skipped
        invalid_result = {
            'title': 'Valid Title',  # Valid title so it won't be skipped
            'authors': ['Valid Author'],
            'arxiv_id': '2301.12345',
            'year': 3000  # Invalid year should trigger validation warning
        }
        
        with patch.object(self.api.logger, 'warning') as mock_warning:
            formatted_results = self.api._response_format([invalid_result], 'arxiv')
            
            # Should still return result but log warning
            assert len(formatted_results) == 1
            mock_warning.assert_called()
            
            # Verify warning message mentions validation
            warning_calls = [call.args[0] for call in mock_warning.call_args_list]
            assert any("Schema validation failed" in call for call in warning_calls)
    
    def test_schema_validation_skips_empty_title(self):
        """Test that items with empty titles are skipped."""
        # Test with empty title that should be skipped
        invalid_result = {
            'title': '',  # Empty title should cause item to be skipped
            'authors': ['Valid Author'],
            'arxiv_id': '2301.12345',
            'year': 2023
        }
        
        with patch.object(self.api.logger, 'warning') as mock_warning:
            formatted_results = self.api._response_format([invalid_result], 'arxiv')
            
            # Should skip the result due to empty title
            assert len(formatted_results) == 0
            mock_warning.assert_called()
            
            # Verify warning message mentions validation and title
            warning_calls = [call.args[0] for call in mock_warning.call_args_list]
            assert any("Schema validation failed" in call and "title is required" in call for call in warning_calls)


class TestArxivSearchAPIEdgeCases:
    """Test edge cases and error conditions for ArxivSearchAPI."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = ArxivSearchAPI()
    
    def test_empty_results_handling(self):
        """Test handling of empty search results."""
        formatted_results = self.api._response_format([], 'arxiv')
        assert formatted_results == []
    
    def test_malformed_author_data(self):
        """Test handling of malformed author data."""
        result_with_bad_authors = {
            'title': 'Test Paper',
            'authors': [None, '', '   ', 'Valid Author'],  # Mix of invalid and valid
            'arxiv_id': '2301.12345',
            'year': 2023
        }
        
        formatted_results = self.api._response_format([result_with_bad_authors], 'arxiv')
        result = formatted_results[0]
        
        # Should only include valid author
        authors = result['authors']
        assert len(authors) == 1
        assert authors[0]['full_name'] == 'Valid Author'
    
    def test_malformed_category_data(self):
        """Test handling of malformed category data."""
        result_with_bad_categories = {
            'title': 'Test Paper',
            'authors': ['Author'],
            'arxiv_id': '2301.12345',
            'year': 2023,
            'categories': [None, '', '   ', 'cs.AI']  # Mix of invalid and valid
        }
        
        formatted_results = self.api._response_format([result_with_bad_categories], 'arxiv')
        result = formatted_results[0]
        
        # Should only include valid category
        categories = result['categories']
        assert len(categories) == 1
        assert categories[0]['category_name'] == 'cs.AI'
    
    def test_missing_arxiv_id(self):
        """Test handling when ArXiv ID is missing."""
        result_without_arxiv_id = {
            'title': 'Test Paper',
            'authors': ['Author'],
            'year': 2023
        }
        
        formatted_results = self.api._response_format([result_without_arxiv_id], 'arxiv')
        result = formatted_results[0]
        
        # Should still create valid result
        assert result['article']['title'] == 'Test Paper'
        
        # Should not have ArXiv ID identifier
        identifiers = result['identifiers']
        arxiv_ids = [id for id in identifiers if id['identifier_type'] == IdentifierType.ARXIV_ID]
        assert len(arxiv_ids) == 0


if __name__ == "__main__":
    pytest.main([__file__])