"""
Unit tests for refactored BioRxivSearchAPI.

This module contains comprehensive tests for the BioRxivSearchAPI class,
including search functionality, parameter validation, result formatting,
and integration with the BaseSearchEngine architecture.
"""

import json
import os
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.search.engine import BioRxivSearchAPI
from src.search.engine.base_engine import BaseSearchEngine, NetworkError
from src.models.enums import IdentifierType, VenueType, CategoryType


class TestBioRxivSearchAPI:
    """Test cases for BioRxivSearchAPI class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = BioRxivSearchAPI()
        
        # Load real template data
        template_path = os.path.join(os.path.dirname(__file__), '..', '..', 'templates', 'temp_biorxiv.json')
        with open(template_path, 'r', encoding='utf-8') as f:
            self.template_data = json.load(f)
        
        # Use first item from template as test data
        self.sample_collection = self.template_data['collection'][0]
        
        # Expected parsed result based on template data
        self.expected_parsed_result = {
            'title': self.sample_collection['title'],
            'abstract': self.sample_collection['abstract'],
            'authors': [author.strip() for author in self.sample_collection['authors'].split(';')],
            'doi': self.sample_collection['doi'],
            'year': datetime.strptime(self.sample_collection['date'], '%Y-%m-%d').year,
            'published_date': self.sample_collection['date'],
            'journal': self.sample_collection['server'],
            'types': ['Preprint'],
            'biorxiv': self.sample_collection
        }
    
    def test_inheritance_from_base_engine(self):
        """Test that BioRxivSearchAPI properly inherits from BaseSearchEngine."""
        assert isinstance(self.api, BaseSearchEngine)
        assert hasattr(self.api, 'search')
        assert hasattr(self.api, '_search')
        assert hasattr(self.api, '_response_format')
        assert hasattr(self.api, 'get_source_name')
    
    def test_initialization(self):
        """Test BioRxivSearchAPI initialization."""
        api = BioRxivSearchAPI()
        
        assert api.source_name == 'biorxiv'
        assert api.max_results_limit == 10000
        assert api.default_results == 50
        assert api.limit == 100  # bioRxiv specific limit
        assert api.base_url == "https://api.biorxiv.org"
    
    def test_get_source_name(self):
        """Test get_source_name method."""
        assert self.api.get_source_name() == 'biorxiv'
    
    @patch('src.search.biorxiv_search.BioRxivSearchAPI.query')
    def test_search_method_basic(self, mock_query):
        """Test basic _search method functionality."""
        # Setup mock
        mock_query.return_value = ([self.expected_parsed_result], {'query': 'test'})
        
        # Execute search
        results, metadata = self.api._search("10.1101/2025.08.04.668552", num_results=10)
        
        # Verify results
        assert len(results) == 1
        assert results[0] == self.expected_parsed_result
        
        # Verify metadata
        assert 'query' in metadata
        
        # Verify method calls
        mock_query.assert_called_once_with(
            query="10.1101/2025.08.04.668552",
            year='',
            num_results=10,
            server='biorxiv'
        )
    
    @patch('src.search.biorxiv_search.BioRxivSearchAPI.query')
    def test_search_with_parameters(self, mock_query):
        """Test _search method with various parameters."""
        # Setup mock
        mock_query.return_value = ([self.expected_parsed_result], {'query': 'test'})
        
        # Execute search with parameters
        results, metadata = self.api._search(
            "test query",
            num_results=50,
            year="2023",
            server="medrxiv"
        )
        
        # Verify query method was called with correct parameters
        mock_query.assert_called_once_with(
            query="test query",
            year="2023",
            num_results=50,
            server="medrxiv"
        )
    
    @patch('src.search.biorxiv_search.BioRxivSearchAPI.query')
    def test_search_network_error_handling(self, mock_query):
        """Test that network errors are properly handled."""
        # Setup mock to raise exception
        mock_query.side_effect = Exception("Network connection failed")
        
        # Verify NetworkError is raised
        with pytest.raises(NetworkError) as exc_info:
            self.api._search("test query")
        
        assert "bioRxiv search failed" in str(exc_info.value)
    
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
        assert article['title'] == self.sample_collection['title']
        assert article['abstract'] == self.sample_collection['abstract']
        assert article['primary_doi'] == self.sample_collection['doi']
        assert article['publication_year'] == datetime.strptime(self.sample_collection['date'], '%Y-%m-%d').year
        assert article['is_open_access'] is True
        assert article['language'] == "eng"
        
        # Verify authors using template data
        authors = result['authors']
        expected_authors = [author.strip() for author in self.sample_collection['authors'].split(';')]
        assert len(authors) == len(expected_authors)
        for i, expected_author in enumerate(expected_authors):
            assert authors[i]['full_name'] == expected_author
            assert authors[i]['author_order'] == i + 1
        
        # Verify venue
        venue = result['venue']
        assert venue['venue_name'] == self.sample_collection['server']
        # Handle enum comparison
        assert venue['venue_type'] == VenueType.PREPRINT_SERVER or venue['venue_type'] == VenueType.PREPRINT_SERVER.value
        
        # Verify identifiers
        identifiers = result['identifiers']
        assert len(identifiers) >= 1  # At least DOI
        
        # Find DOI identifier
        doi_identifier = next((id for id in identifiers if 
                              id['identifier_type'] == IdentifierType.DOI or 
                              id['identifier_type'] == IdentifierType.DOI.value), None)
        assert doi_identifier is not None
        assert doi_identifier['identifier_value'] == self.sample_collection['doi']
        assert doi_identifier['is_primary'] is True
        
        # Verify categories using template data
        categories = result['categories']
        assert len(categories) == 1
        assert categories[0]['category_name'] == self.sample_collection['category']
        # Handle enum comparison
        assert (categories[0]['category_type'] == CategoryType.OTHER or 
               categories[0]['category_type'] == CategoryType.OTHER.value)
        
        # Verify publication types
        publication_types = result['publication_types']
        assert len(publication_types) == 1
        assert publication_types[0]['type_name'] == 'Preprint'
        
        # Verify source specific data
        source_specific = result['source_specific']
        assert source_specific['source'] == 'biorxiv'
        assert 'raw_data' in source_specific
        assert source_specific['server'] == self.sample_collection['server']
        assert source_specific['version'] == self.sample_collection['version']
        assert source_specific['license'] == self.sample_collection['license']
        assert source_specific['jatsxml'] == self.sample_collection['jatsxml']
        assert source_specific['author_corresponding'] == self.sample_collection['author_corresponding']
        assert source_specific['author_corresponding_institution'] == self.sample_collection['author_corresponding_institution']
    
    def test_response_format_no_doi(self):
        """Test _response_format when DOI is not available."""
        # Create test data without DOI
        raw_result = self.expected_parsed_result.copy()
        raw_result['doi'] = ''
        raw_result['biorxiv'] = self.sample_collection.copy()
        raw_result['biorxiv']['doi'] = ''
        
        formatted_results = self.api._response_format([raw_result])
        result = formatted_results[0]
        
        # Should still create valid result
        assert result['article']['title'] == self.sample_collection['title']
        
        # Should not have DOI identifier
        identifiers = result['identifiers']
        doi_ids = [id for id in identifiers if 
                  id['identifier_type'] == IdentifierType.DOI or 
                  id['identifier_type'] == IdentifierType.DOI.value]
        assert len(doi_ids) == 0
    
    def test_response_format_missing_fields(self):
        """Test _response_format with missing optional fields."""
        # Test data with minimal fields
        minimal_result = {
            'title': 'Minimal Paper',
            'authors': ['Single Author'],
            'year': 2023,
            'types': ['Preprint'],
            'biorxiv': {'category': 'biology'}
        }
        
        formatted_results = self.api._response_format([minimal_result])
        result = formatted_results[0]
        
        # Verify it still creates a valid structure
        assert result['article']['title'] == 'Minimal Paper'
        assert len(result['authors']) == 1
        assert result['authors'][0]['full_name'] == 'Single Author'
        
        # Verify venue defaults
        venue = result['venue']
        assert venue['venue_name'] == 'bioRxiv'  # Default when no journal
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
        assert self.api.validate_params("10.1101/2025.08.04.668552", num_results=100) is True
        assert self.api.validate_params("test query", server="medrxiv") is True
    
    def test_validate_params_inherits_base_validation(self):
        """Test that bioRxiv validation includes base class validation."""
        # These should fail due to base class validation
        assert self.api.validate_params("") is False
        assert self.api.validate_params("test", num_results=0) is False
        assert self.api.validate_params("test", num_results=-1) is False
        assert self.api.validate_params("test", year="invalid") is False
    
    @patch('src.search.biorxiv_search.BioRxivSearchAPI._search')
    @patch('src.search.biorxiv_search.BioRxivSearchAPI._response_format')
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
        assert final_metadata['source'] == 'biorxiv'
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
                query="10.1101/2025.08.04.668552",
                num_results=10,
                year="2023",
                server="biorxiv"
            )
            
            # Verify legacy format is returned
            assert len(results) == 1
            assert results[0] == self.expected_parsed_result
            assert returned_metadata == metadata
            
            # Verify new search method was called with correct parameters
            mock_search.assert_called_once_with(
                "10.1101/2025.08.04.668552",
                num_results=10,
                year="2023",
                server="biorxiv"
            )
    
    def test_search_with_zero_results(self):
        """Test search behavior when num_results is 0."""
        with patch.object(self.api, 'query') as mock_query:
            mock_query.return_value = ([], {'query': 'test'})
            
            results, metadata = self.api._search("test", num_results=0)
            
            assert results == []
            assert metadata['query'] == 'test'
    
    def test_schema_validation_in_format(self):
        """Test that schema validation is performed during formatting."""
        # Test with invalid data that should trigger validation warnings but not be skipped
        invalid_result = {
            'title': 'Valid Title',  # Valid title so it won't be skipped
            'authors': ['Valid Author'],
            'year': 3000,  # Invalid year should trigger validation warning
            'types': ['Preprint'],
            'biorxiv': {'category': 'biology'}
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
            'year': 2023,
            'types': ['Preprint'],
            'biorxiv': {'category': 'biology'}
        }
        
        with patch.object(self.api.logger, 'warning') as mock_warning:
            formatted_results = self.api._response_format([invalid_result])
            
            # Should skip the result due to empty title
            assert len(formatted_results) == 0
            mock_warning.assert_called()


class TestBioRxivSearchAPIEdgeCases:
    """Test edge cases and error conditions for BioRxivSearchAPI."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = BioRxivSearchAPI()
    
    def test_empty_results_handling(self):
        """Test handling of empty search results."""
        formatted_results = self.api._response_format([])
        assert formatted_results == []
    
    def test_malformed_author_data(self):
        """Test handling of malformed author data."""
        result_with_bad_authors = {
            'title': 'Test Paper',
            'authors': [None, '', '   ', 'Valid Author'],  # Mix of invalid and valid
            'year': 2023,
            'types': ['Preprint'],
            'biorxiv': {'category': 'biology'}
        }
        
        formatted_results = self.api._response_format([result_with_bad_authors])
        result = formatted_results[0]
        
        # Should only include valid author
        authors = result['authors']
        assert len(authors) == 1
        assert authors[0]['full_name'] == 'Valid Author'
    
    def test_missing_category_data(self):
        """Test handling when category data is missing."""
        result_without_category = {
            'title': 'Test Paper',
            'authors': ['Author'],
            'year': 2023,
            'types': ['Preprint'],
            'biorxiv': {}  # No category
        }
        
        formatted_results = self.api._response_format([result_without_category])
        result = formatted_results[0]
        
        # Should still create valid result
        assert result['article']['title'] == 'Test Paper'
        
        # Should not have categories
        categories = result['categories']
        assert len(categories) == 0


if __name__ == "__main__":
    pytest.main([__file__])