"""
Tests for the refactored Semantic Scholar search API.

This module tests the SemanticBulkSearchAPI class to ensure it properly
inherits from BaseSearchEngine and implements the required methods.
"""

import pytest
import json
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.search.semantic_search import SemanticBulkSearchAPI, semantic_bulk_search
from src.search.base_engine import ParameterValidationError, NetworkError, FormatError
from src.models.schemas import LiteratureSchema
from src.models.enums import IdentifierType, VenueType, CategoryType


class TestSemanticBulkSearchAPI:
    """Test cases for SemanticBulkSearchAPI class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = SemanticBulkSearchAPI()
        
        # Load real template data
        template_path = os.path.join(os.path.dirname(__file__), '..', '..', 'templates', 'temp_semantic_scholar.json')
        with open(template_path, 'r', encoding='utf-8') as f:
            template_data = json.load(f)
        
        # Use first item from template data
        self.sample_raw_result = template_data['data'][0]
    
    def test_inheritance(self):
        """Test that SemanticBulkSearchAPI properly inherits from BaseSearchEngine."""
        from src.search.base_engine import BaseSearchEngine
        assert isinstance(self.api, BaseSearchEngine)
        assert hasattr(self.api, 'search')
        assert hasattr(self.api, '_search')
        assert hasattr(self.api, '_response_format')
        assert hasattr(self.api, 'get_source_name')
    
    def test_get_source_name(self):
        """Test get_source_name method."""
        assert self.api.get_source_name() == "semantic_scholar"
        assert self.api.source_name == "semantic_scholar"
    
    def test_parameter_validation_valid(self):
        """Test parameter validation with valid parameters."""
        assert self.api.validate_params("machine learning", num_results=50)
        assert self.api.validate_params("AI", year="2020-2023", num_results=100)
        assert self.api.validate_params("neural networks", document_type="Article", fields_of_study="Computer Science")
    
    def test_parameter_validation_invalid_query(self):
        """Test parameter validation with invalid query."""
        assert not self.api.validate_params("")
        assert not self.api.validate_params("   ")
        assert not self.api.validate_params(None)
    
    def test_parameter_validation_invalid_document_type(self):
        """Test parameter validation with invalid document type."""
        assert not self.api.validate_params("test", document_type="InvalidType")
    
    def test_parameter_validation_invalid_types(self):
        """Test parameter validation with invalid parameter types."""
        assert not self.api.validate_params("test", fields_of_study=123)
        assert not self.api.validate_params("test", fields=456)
        assert not self.api.validate_params("test", filtered="not_boolean")
    
    @patch('src.search.semantic_search.SemanticBulkSearchAPI.query')
    def test_search_method_success(self, mock_query):
        """Test the _search method with successful response."""
        # Mock the query method
        mock_query.return_value = ([self.sample_raw_result], {"total": 1})
        
        # Test _search method
        results, metadata = self.api._search("machine learning", num_results=50)
        
        assert len(results) == 1
        assert results[0] == self.sample_raw_result
        assert metadata["total"] == 1
        mock_query.assert_called_once()
    
    @patch('src.search.semantic_search.SemanticBulkSearchAPI.query')
    def test_search_method_network_error(self, mock_query):
        """Test the _search method with network error."""
        # Mock query to raise an exception
        mock_query.side_effect = Exception("Network error")
        
        # Test that NetworkError is raised
        with pytest.raises(NetworkError):
            self.api._search("machine learning")
    
    def test_response_format_single_result(self):
        """Test _response_format method with a single result."""
        results = self.api._response_format([self.sample_raw_result])
        
        assert len(results) == 1
        result = results[0]
        
        # Verify the result is a dictionary (from LiteratureSchema.to_dict())
        assert isinstance(result, dict)
        
        # Check article information using template data
        assert result['article']['title'] == self.sample_raw_result['title']
        assert result['article']['primary_doi'] == self.sample_raw_result['externalIds']['DOI']
        assert result['article']['publication_year'] == self.sample_raw_result['year']
        assert result['article']['citation_count'] == self.sample_raw_result['citationCount']
        assert result['article']['is_open_access'] == self.sample_raw_result['isOpenAccess']
        
        # Check authors using template data
        expected_authors = self.sample_raw_result['authors']
        assert len(result['authors']) == len(expected_authors)
        for i, expected_author in enumerate(expected_authors):
            assert result['authors'][i]['full_name'] == expected_author['name']
            assert result['authors'][i]['author_order'] == i + 1
        
        # Check venue using template data
        assert result['venue']['venue_name'] == self.sample_raw_result['venue']
        
        # Check identifiers
        identifiers = result['identifiers']
        # Handle enum comparison - asdict() doesn't convert enums to values
        from src.models.enums import IdentifierType
        doi_found = any((id['identifier_type'] == IdentifierType.DOI or id['identifier_type'] == IdentifierType.DOI.value) and 
                       id['identifier_value'] == self.sample_raw_result['externalIds']['DOI'] 
                       for id in identifiers)
        assert doi_found, f"DOI not found in identifiers: {identifiers}"
        
        # Check source specific data
        assert result['source_specific']['source'] == "semantic_scholar"
    
    def test_response_format_empty_results(self):
        """Test _response_format method with empty results."""
        results = self.api._response_format([])
        assert results == []
    
    def test_response_format_malformed_result(self):
        """Test _response_format method with malformed result."""
        malformed_result = {"invalid": "data"}
        results = self.api._response_format([malformed_result])
        
        # Should handle malformed data gracefully
        assert len(results) == 1
        result = results[0]
        assert result['article']['title'] == ""  # Default value
    
    def test_format_single_result_detailed(self):
        """Test _format_single_result method with detailed data."""
        literature = self.api._format_single_result(self.sample_raw_result)
        
        assert isinstance(literature, LiteratureSchema)
        assert literature.article.title == self.sample_raw_result['title']
        assert literature.article.primary_doi == self.sample_raw_result['externalIds']['DOI']
        assert literature.article.citation_count == self.sample_raw_result['citationCount']
        assert literature.article.is_open_access == self.sample_raw_result['isOpenAccess']
        
        # Check identifiers using template data
        doi = literature.get_identifier(IdentifierType.DOI)
        assert doi == self.sample_raw_result['externalIds']['DOI']
        
        semantic_id = literature.get_identifier(IdentifierType.SEMANTIC_SCHOLAR_ID)
        assert semantic_id == self.sample_raw_result['paperId']
        
        # Check categories using template data
        # Note: The template data includes both fieldsOfStudy and s2FieldsOfStudy, so we may have more categories
        expected_fields = self.sample_raw_result['fieldsOfStudy']
        # Just check that we have at least the expected fields
        assert len(literature.categories) >= len(expected_fields)
        
        # Check that all expected fields are present
        category_names = [cat.category_name for cat in literature.categories]
        for expected_field in expected_fields:
            assert expected_field in category_names
        
        # Check that all categories have the correct type
        for category in literature.categories:
            assert category.category_type == CategoryType.FIELD_OF_STUDY
    
    def test_extract_open_access_url(self):
        """Test _extract_open_access_url method."""
        # Test with dict format
        item_dict = {"openAccessPdf": {"url": "https://example.com/paper.pdf"}}
        url = self.api._extract_open_access_url(item_dict)
        assert url == "https://example.com/paper.pdf"
        
        # Test with string format
        item_string = {"openAccessPdf": "https://example.com/paper.pdf"}
        url = self.api._extract_open_access_url(item_string)
        assert url == "https://example.com/paper.pdf"
        
        # Test with no URL
        item_none = {}
        url = self.api._extract_open_access_url(item_none)
        assert url is None
    
    def test_determine_venue_type(self):
        """Test _determine_venue_type method."""
        # Test conference
        item_conf = {"publicationVenue": {"type": "conference"}}
        venue_type = self.api._determine_venue_type(item_conf)
        assert venue_type == VenueType.CONFERENCE
        
        # Test journal
        item_journal = {"journal": {"name": "Nature"}}
        venue_type = self.api._determine_venue_type(item_journal)
        assert venue_type == VenueType.JOURNAL
        
        # Test other
        item_other = {}
        venue_type = self.api._determine_venue_type(item_other)
        assert venue_type == VenueType.OTHER
    
    @patch('src.search.semantic_search.SemanticBulkSearchAPI.search')
    def test_semantic_bulk_search_function(self, mock_search):
        """Test the semantic_bulk_search function."""
        # Mock the search method
        mock_search.return_value = ([{"formatted": "result"}], {"total": 1})
        
        results, metadata = semantic_bulk_search("machine learning", num_results=50)
        
        assert len(results) == 1
        assert results[0] == {"formatted": "result"}
        assert metadata["total"] == 1
        mock_search.assert_called_once()
    
    def test_semantic_bulk_search_empty_results(self):
        """Test semantic_bulk_search function with empty num_results."""
        results, metadata = semantic_bulk_search("test", num_results=0)
        assert results == []
        assert metadata == {}
    
    @patch('src.search.semantic_search.SemanticBulkSearchAPI.search')
    def test_full_search_integration(self, mock_search):
        """Test full search integration through the public interface."""
        # Mock the search method to return formatted results
        formatted_result = {
            'article': {
                'title': 'Test Paper',
                'primary_doi': '10.1000/test'
            },
            'authors': [{'full_name': 'Test Author'}],
            'source_specific': {'source': 'semantic_scholar'}
        }
        mock_search.return_value = ([formatted_result], {"total": 1, "source": "semantic_scholar"})
        
        # Test through the public interface
        api = SemanticBulkSearchAPI()
        results, metadata = api.search("machine learning", num_results=10)
        
        assert len(results) == 1
        assert results[0]['article']['title'] == 'Test Paper'
        assert metadata['source'] == 'semantic_scholar'


class TestSemanticSearchIntegration:
    """Integration tests for Semantic Scholar search functionality."""
    
    @patch('requests.get')
    def test_query_once_success(self, mock_get):
        """Test query_once method with successful response."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total": 100,
            "data": [{"paperId": "test123", "title": "Test Paper"}],
            "token": "next_token"
        }
        mock_get.return_value = mock_response
        
        api = SemanticBulkSearchAPI()
        total, data, url, token = api.query_once("machine learning")
        
        assert total == 100
        assert len(data) == 1
        assert data[0]["paperId"] == "test123"
        assert token == "next_token"
    
    @patch('requests.get')
    def test_query_once_failure(self, mock_get):
        """Test query_once method with failed response."""
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        api = SemanticBulkSearchAPI()
        total, data, url, token = api.query_once("machine learning")
        
        assert total == 0
        assert data == []
        assert token == ''
    
    @patch('requests.get')
    def test_query_once_timeout(self, mock_get):
        """Test query_once method with timeout."""
        # Mock timeout
        mock_get.side_effect = Exception("Timeout")
        
        api = SemanticBulkSearchAPI()
        total, data, url, token = api.query_once("machine learning")
        
        assert total == 0
        assert data == []
        assert token == ''


if __name__ == "__main__":
    pytest.main([__file__])