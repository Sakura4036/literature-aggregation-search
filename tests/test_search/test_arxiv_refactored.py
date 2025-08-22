"""
Unit tests for refactored ArxivSearchAPI.

This module contains comprehensive tests for the ArxivSearchAPI class,
including search functionality, parameter validation, result formatting,
and integration with the BaseSearchEngine architecture.
"""

import pytest
import json
import os
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
        
        # Load real template data
        template_path = os.path.join(os.path.dirname(__file__), '..', '..', 'templates', 'temp_arxiv.json')
        with open(template_path, 'r', encoding='utf-8') as f:
            self.template_data = json.load(f)
        
        # Use first item from template as test data
        self.sample_result = self.template_data[0]
        
        # Mock ArXiv result object based on template data
        self.mock_arxiv_result = Mock()
        self.mock_arxiv_result.title = self.sample_result['title']
        self.mock_arxiv_result.summary = self.sample_result['abstract']
        self.mock_arxiv_result.authors = [Mock(name=name) for name in self.sample_result['authors']]
        self.mock_arxiv_result.doi = self.sample_result['doi']
        self.mock_arxiv_result.get_short_id.return_value = self.sample_result['arxiv_id']
        self.mock_arxiv_result.published = datetime.strptime(self.sample_result['published_date'], '%Y-%m-%d')
        self.mock_arxiv_result.updated = datetime.strptime(self.sample_result['updated_date'], '%Y-%m-%d')
        self.mock_arxiv_result.journal_ref = self.sample_result['journal']
        self.mock_arxiv_result.entry_id = self.sample_result['url']
        self.mock_arxiv_result.categories = self.sample_result['categories']
        self.mock_arxiv_result.pdf_url = self.sample_result['pdf_url']
        
        # Expected parsed result based on template data
        self.expected_parsed_result = {
            'title': self.sample_result['title'],
            'abstract': self.sample_result['abstract'],
            'authors': self.sample_result['authors'],
            'doi': self.sample_result['doi'],
            'arxiv_id': self.sample_result['arxiv_id'],
            'year': self.sample_result['year'],
            'published_date': self.sample_result['published_date'],
            'updated_date': self.sample_result['updated_date'],
            'journal': self.sample_result['journal'],
            'url': self.sample_result['url'],
            'categories': self.sample_result['categories'],
            'pdf_url': self.sample_result['pdf_url'],
            'arxiv': self.sample_result['arxiv']
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
        assert 'categories' in result
        assert 'source_specific' in result
        
        # Verify article information using template data
        article = result['article']
        assert article['title'] == self.sample_result['title']
        assert article['abstract'] == self.sample_result['abstract']
        assert article['primary_doi'] == self.sample_result['doi']
        assert article['publication_year'] == self.sample_result['year']
        assert article['is_open_access'] is True
        
        # Verify authors using template data
        authors = result['authors']
        assert len(authors) == len(self.sample_result['authors'])
        for i, expected_author in enumerate(self.sample_result['authors']):
            assert authors[i]['full_name'] == expected_author
            assert authors[i]['author_order'] == i + 1
        
        # Verify venue
        venue = result['venue']
        assert venue['venue_name'] == self.sample_result['journal']
        # Handle enum comparison - asdict() doesn't convert enums to values
        assert venue['venue_type'] == VenueType.PREPRINT_SERVER or venue['venue_type'] == VenueType.PREPRINT_SERVER.value
        
        # Verify identifiers
        identifiers = result['identifiers']
        assert len(identifiers) >= 2  # DOI and ArXiv ID
        
        # Find DOI identifier - handle enum comparison
        doi_identifier = next((id for id in identifiers if 
                              id['identifier_type'] == IdentifierType.DOI or 
                              id['identifier_type'] == IdentifierType.DOI.value), None)
        assert doi_identifier is not None
        assert doi_identifier['identifier_value'] == self.sample_result['doi']
        assert doi_identifier['is_primary'] is True
        
        # Find ArXiv ID identifier - handle enum comparison
        arxiv_identifier = next((id for id in identifiers if 
                                id['identifier_type'] == IdentifierType.ARXIV_ID or 
                                id['identifier_type'] == IdentifierType.ARXIV_ID.value), None)
        assert arxiv_identifier is not None
        assert arxiv_identifier['identifier_value'] == self.sample_result['arxiv_id']
        
        # Verify categories using template data
        categories = result['categories']
        assert len(categories) == len(self.sample_result['categories'])
        for i, expected_category in enumerate(self.sample_result['categories']):
            assert categories[i]['category_name'] == expected_category
            # Handle enum comparison
            assert (categories[i]['category_type'] == CategoryType.ARXIV_CATEGORY or 
                   categories[i]['category_type'] == CategoryType.ARXIV_CATEGORY.value)
        
        # Verify source specific data
        source_specific = result['source_specific']
        assert source_specific['source'] == 'arxiv'
        assert 'raw_data' in source_specific
        assert 'pdf_url' in source_specific
    
    def test_response_format_no_doi(self):
        """Test _response_format when DOI is not available."""
        # Use second template item which has no DOI
        raw_result = self.template_data[1].copy()  # BERT paper has empty DOI
        
        formatted_results = self.api._response_format([raw_result])
        result = formatted_results[0]
        
        # Verify ArXiv ID becomes primary when no DOI
        identifiers = result['identifiers']
        arxiv_identifier = next((id for id in identifiers if 
                                id['identifier_type'] == IdentifierType.ARXIV_ID or 
                                id['identifier_type'] == IdentifierType.ARXIV_ID.value), None)
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
        
        formatted_results = self.api._response_format([minimal_result])
        result = formatted_results[0]
        
        # Verify it still creates a valid structure
        assert result['article']['title'] == 'Minimal Paper'
        assert len(result['authors']) == 1
        assert result['authors'][0]['full_name'] == 'Single Author'
        assert len(result['categories']) == 0
        
        # Verify venue defaults
        venue = result['venue']
        assert venue['venue_name'] == 'arXiv'  # Default when no journal
        # Handle enum comparison
        assert (venue['venue_type'] == VenueType.PREPRINT_SERVER or 
               venue['venue_type'] == VenueType.PREPRINT_SERVER.value)
    
    def test_response_format_error_handling(self):
        """Test _response_format error handling for malformed data."""
        # Test with malformed data
        malformed_result = {'invalid': 'data'}
        
        # Should not raise exception, but log warning and continue
        formatted_results = self.api._response_format([malformed_result])
        
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
            formatted_results = self.api._response_format([invalid_result])
            
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
            formatted_results = self.api._response_format([invalid_result])
            
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
        formatted_results = self.api._response_format([])
        assert formatted_results == []
    
    def test_malformed_author_data(self):
        """Test handling of malformed author data."""
        result_with_bad_authors = {
            'title': 'Test Paper',
            'authors': [None, '', '   ', 'Valid Author'],  # Mix of invalid and valid
            'arxiv_id': '2301.12345',
            'year': 2023
        }
        
        formatted_results = self.api._response_format([result_with_bad_authors])
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
        
        formatted_results = self.api._response_format([result_with_bad_categories])
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
        
        formatted_results = self.api._response_format([result_without_arxiv_id])
        result = formatted_results[0]
        
        # Should still create valid result
        assert result['article']['title'] == 'Test Paper'
        
        # Should not have ArXiv ID identifier
        identifiers = result['identifiers']
        arxiv_ids = [id for id in identifiers if 
                    id['identifier_type'] == IdentifierType.ARXIV_ID or 
                    id['identifier_type'] == IdentifierType.ARXIV_ID.value]
        assert len(arxiv_ids) == 0


if __name__ == "__main__":
    pytest.main([__file__])