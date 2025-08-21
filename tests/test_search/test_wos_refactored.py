"""
Tests for the refactored WoS search API.

This module tests the WosSearchAPI class to ensure it properly implements
the BaseSearchEngine interface and correctly formats WoS data into
LiteratureSchema format.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.search.wos_search import WosSearchAPI, WosApiKeyManager
from src.search.base_engine import BaseSearchEngine, NetworkError, FormatError
from src.models.schemas import LiteratureSchema
from src.models.enums import IdentifierType, VenueType, CategoryType, PublicationTypeSource


class TestWosSearchAPI:
    """Test cases for WosSearchAPI class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api = WosSearchAPI(api_keys=['test_key_1', 'test_key_2'])
        
        # Load test data
        with open('templates/temp_wos.json', 'r', encoding='utf-8') as f:
            self.test_data = json.load(f)
    
    def test_inheritance(self):
        """Test that WosSearchAPI properly inherits from BaseSearchEngine."""
        assert isinstance(self.api, BaseSearchEngine)
        assert hasattr(self.api, 'search')
        assert hasattr(self.api, '_search')
        assert hasattr(self.api, '_response_format')
        assert hasattr(self.api, 'get_source_name')
    
    def test_get_source_name(self):
        """Test get_source_name method."""
        assert self.api.get_source_name() == "wos"
    
    def test_initialization(self):
        """Test proper initialization of WosSearchAPI."""
        # Test with API keys
        api_with_keys = WosSearchAPI(api_keys=['key1', 'key2'])
        assert api_with_keys.api_keys == ['key1', 'key2']
        assert api_with_keys.source_name == "wos"
        
        # Test without API keys
        api_without_keys = WosSearchAPI()
        assert api_without_keys.api_keys == []
    
    @patch('src.search.wos_search.WosSearchAPI.query')
    def test_search_method(self, mock_query):
        """Test the _search method."""
        # Mock the query method to return test data
        mock_query.return_value = (self.test_data['hits'], {'total': 2})
        
        # Test _search method
        results, metadata = self.api._search("test query", num_results=10)
        
        assert len(results) == 2
        assert metadata['total'] == 2
        mock_query.assert_called_once_with(
            "test query", 'TS', '', '', 10, 'RS+D', 'WOK'
        )
    
    @patch('src.search.wos_search.WosSearchAPI.query')
    def test_search_with_parameters(self, mock_query):
        """Test _search method with various parameters."""
        mock_query.return_value = ([], {'total': 0})
        
        # Test with custom parameters
        self.api._search(
            "test query",
            query_type='TI',
            year='2020-2023',
            document_type='Article',
            num_results=100,
            sort_field='PY+D',
            db='WOS'
        )
        
        mock_query.assert_called_once_with(
            "test query", 'TI', '2020-2023', 'Article', 100, 'PY+D', 'WOS'
        )
    
    @patch('src.search.wos_search.WosSearchAPI.query')
    def test_search_network_error(self, mock_query):
        """Test _search method handles network errors."""
        mock_query.side_effect = Exception("Network error")
        
        with pytest.raises(NetworkError):
            self.api._search("test query")
    
    def test_response_format_basic(self):
        """Test basic response formatting."""
        # Use the test data from templates
        raw_results = [
            {
                'title': 'Test Article',
                'abstract': 'Test abstract',
                'doi': '10.1234/test',
                'pmid': '12345',
                'issn': '1234-5678',
                'eissn': '8765-4321',
                'year': 2023,
                'published_date': '2023-01-01',
                'types': ['Article'],
                'authors': ['Smith, J', 'Doe, A'],
                'journal': 'Test Journal',
                'volume': '10',
                'issue': '2',
                'wos': {
                    'uid': 'WOS:123456789',
                    'citations': [{'db': 'WOS', 'count': 5}],
                    'source': {
                        'pages': {'range': '123-130'}
                    },
                    'sourceTypes': ['Article'],
                    'links': {'record': 'http://example.com'},
                    'keywords': {'authorKeywords': ['keyword1', 'keyword2']}
                }
            }
        ]
        
        formatted_results = self.api._response_format(raw_results)
        
        assert len(formatted_results) == 1
        result = formatted_results[0]
        
        # Verify the structure matches LiteratureSchema
        assert 'article' in result
        assert 'authors' in result
        assert 'venue' in result
        assert 'publication' in result
        assert 'identifiers' in result
        assert 'categories' in result
        assert 'publication_types' in result
        assert 'source_specific' in result
        
        # Verify article data
        article = result['article']
        assert article['title'] == 'Test Article'
        assert article['abstract'] == 'Test abstract'
        assert article['primary_doi'] == '10.1234/test'
        assert article['publication_year'] == 2023
        assert article['citation_count'] == 5
        
        # Verify authors
        authors = result['authors']
        assert len(authors) == 2
        assert authors[0]['full_name'] == 'Smith, J'
        assert authors[0]['author_order'] == 1
        assert authors[1]['full_name'] == 'Doe, A'
        assert authors[1]['author_order'] == 2
        
        # Verify venue
        venue = result['venue']
        assert venue['venue_name'] == 'Test Journal'
        assert venue['venue_type'] == VenueType.JOURNAL  # The dataclass stores the enum object
        assert venue['issn_print'] == '1234-5678'
        assert venue['issn_electronic'] == '8765-4321'
        
        # Verify publication
        publication = result['publication']
        assert publication['volume'] == '10'
        assert publication['issue'] == '2'
        assert publication['page_range'] == '123-130'
        
        # Verify identifiers
        identifiers = result['identifiers']
        assert len(identifiers) == 3  # DOI, PMID, WOS_UID
        
        doi_identifier = next((i for i in identifiers if i['identifier_type'] == IdentifierType.DOI), None)
        assert doi_identifier is not None
        assert doi_identifier['identifier_value'] == '10.1234/test'
        assert doi_identifier['is_primary'] is True
        
        pmid_identifier = next((i for i in identifiers if i['identifier_type'] == IdentifierType.PMID), None)
        assert pmid_identifier is not None
        assert pmid_identifier['identifier_value'] == '12345'
        
        wos_identifier = next((i for i in identifiers if i['identifier_type'] == IdentifierType.WOS_UID), None)
        assert wos_identifier is not None
        assert wos_identifier['identifier_value'] == 'WOS:123456789'
        
        # Verify categories
        categories = result['categories']
        assert len(categories) == 1
        assert categories[0]['category_name'] == 'Article'
        assert categories[0]['category_type'] == CategoryType.WOS_CATEGORY
        
        # Verify publication types
        pub_types = result['publication_types']
        assert len(pub_types) == 1
        assert pub_types[0]['type_name'] == 'Article'
        assert pub_types[0]['source_type'] == PublicationTypeSource.WOS
        
        # Verify source specific data
        source_specific = result['source_specific']
        assert source_specific['source'] == 'wos'
        assert source_specific['wos_uid'] == 'WOS:123456789'
        assert 'raw_data' in source_specific
    
    def test_response_format_with_template_data(self):
        """Test response formatting with actual template data."""
        # Process the raw WoS data from template
        raw_results = []
        for hit in self.test_data['hits']:
            # Convert WoS API format to our internal format
            identifiers = hit.get('identifiers', {})
            authors = []
            if hit.get('names', {}).get('authors'):
                authors = [author.get('displayName', '') for author in hit['names']['authors']]
            
            types = hit.get('types', [])
            if isinstance(types, str):
                types = [types]
            
            year = hit['source'].get('publishYear')
            month = hit['source'].get('publishMonth')
            published_date = None
            if year and month:
                month_map = {
                    'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04',
                    'MAY': '05', 'JUN': '06', 'JUL': '07', 'AUG': '08',
                    'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
                }
                month_num = month_map.get(month, '01')
                published_date = f"{year}-{month_num}"
            
            format_paper = {
                'title': hit.get('title', ''),
                'abstract': hit.get('abstract', ''),
                'doi': identifiers.get('doi', ''),
                'pmid': identifiers.get('pmid', ''),
                'issn': identifiers.get('issn', ''),
                'eissn': identifiers.get('eissn', ''),
                'year': year,
                'published_date': published_date,
                'types': types,
                'authors': authors,
                'journal': hit['source'].get('sourceTitle', ''),
                'volume': hit['source'].get('volume', ''),
                'issue': hit['source'].get('issue', ''),
                'wos': hit
            }
            raw_results.append(format_paper)
        
        formatted_results = self.api._response_format(raw_results)
        
        assert len(formatted_results) == 2
        
        # Check first result
        result1 = formatted_results[0]
        assert result1['article']['title'] == "'EPITAFIO'"
        assert result1['venue']['venue_name'] == "CUADERNOS HISPANOAMERICANOS"
        assert len(result1['authors']) == 1
        assert result1['authors'][0]['full_name'] == "TOMLINSON, C"
        
        # Check second result
        result2 = formatted_results[1]
        assert result2['article']['title'] == "Mapping the land of 'I-don't remember': For a re-evaluation of La 'Historia oficial'"
        assert result2['article']['primary_doi'] == "10.3828/bhs.81.2.5"
        assert result2['venue']['venue_name'] == "BULLETIN OF HISPANIC STUDIES"
        assert len(result2['authors']) == 1
        assert result2['authors'][0]['full_name'] == "Tomlinson, E"
    
    def test_response_format_empty_results(self):
        """Test response formatting with empty results."""
        formatted_results = self.api._response_format([])
        assert formatted_results == []
    
    def test_response_format_malformed_data(self):
        """Test response formatting handles malformed data gracefully."""
        malformed_results = [
            {},  # Empty dict
            {'title': ''},  # Missing required fields
            {'title': 'Valid Title', 'authors': None},  # None authors
        ]
        
        formatted_results = self.api._response_format(malformed_results)
        
        # Should handle malformed data gracefully and continue processing
        assert isinstance(formatted_results, list)
        # Some results might be filtered out due to validation errors
        assert len(formatted_results) <= len(malformed_results)
    
    def test_extract_citation_count(self):
        """Test citation count extraction."""
        # Test with valid citation data
        wos_data = {
            'citations': [
                {'db': 'WOS', 'count': 10},
                {'db': 'OTHER', 'count': 5}
            ]
        }
        count = self.api._extract_citation_count(wos_data)
        assert count == 10
        
        # Test with no WOS citation
        wos_data = {
            'citations': [
                {'db': 'OTHER', 'count': 5}
            ]
        }
        count = self.api._extract_citation_count(wos_data)
        assert count == 0
        
        # Test with empty citations
        wos_data = {'citations': []}
        count = self.api._extract_citation_count(wos_data)
        assert count == 0
        
        # Test with no citations key
        wos_data = {}
        count = self.api._extract_citation_count(wos_data)
        assert count == 0
    
    def test_extract_page_range(self):
        """Test page range extraction."""
        # Test with valid page data
        wos_data = {
            'source': {
                'pages': {
                    'range': '123-130',
                    'begin': '123',
                    'end': '130'
                }
            }
        }
        page_range = self.api._extract_page_range(wos_data)
        assert page_range == '123-130'
        
        # Test with no pages
        wos_data = {'source': {}}
        page_range = self.api._extract_page_range(wos_data)
        assert page_range is None
        
        # Test with no source
        wos_data = {}
        page_range = self.api._extract_page_range(wos_data)
        assert page_range is None
    
    @patch('src.search.wos_search.WosSearchAPI._search')
    @patch('src.search.wos_search.WosSearchAPI._response_format')
    def test_backward_compatible_search(self, mock_format, mock_search):
        """Test that the public search method maintains backward compatibility."""
        # Mock the internal methods
        mock_search.return_value = ([{'test': 'data'}], {'total': 1})
        mock_format.return_value = [{'formatted': 'data'}]
        
        # Call the public search method with old-style parameters
        results, metadata = self.api.search(
            query="test query",
            query_type='TI',
            year='2020',
            document_type='Article',
            limit=50,
            sort_field='PY+D',
            db='WOS'
        )
        
        # Verify the methods were called correctly
        mock_search.assert_called_once()
        mock_format.assert_called_once_with([{'test': 'data'}])
        
        # Verify the results
        assert results == [{'formatted': 'data'}]
        assert 'source' in metadata
        assert metadata['source'] == 'wos'
    
    def test_parameter_validation(self):
        """Test parameter validation."""
        # Test valid parameters
        assert self.api.validate_params("test query", num_results=50)
        
        # Test invalid query
        assert not self.api.validate_params("", num_results=50)
        assert not self.api.validate_params(None, num_results=50)
        
        # Test invalid num_results
        assert not self.api.validate_params("test query", num_results=0)
        assert not self.api.validate_params("test query", num_results=-1)
        assert not self.api.validate_params("test query", num_results=20000)  # Exceeds limit


class TestWosApiKeyManager:
    """Test cases for WosApiKeyManager class."""
    
    def setup_method(self):
        """Reset singleton for each test."""
        # Reset the singleton instance
        WosApiKeyManager._instance = None
    
    def test_singleton_pattern(self):
        """Test that WosApiKeyManager follows singleton pattern."""
        manager1 = WosApiKeyManager(['key1', 'key2'])
        manager2 = WosApiKeyManager(['key3', 'key4'])
        
        # Should be the same instance
        assert manager1 is manager2
    
    def test_key_rotation(self):
        """Test API key rotation functionality."""
        manager = WosApiKeyManager(['key1', 'key2', 'key3'])
        
        # Get keys in sequence
        key1 = manager.get_next_available_key()
        manager.increment_usage(key1)
        
        key2 = manager.get_next_available_key()
        manager.increment_usage(key2)
        
        # Should rotate through keys
        assert key1 in ['key1', 'key2', 'key3']
        assert key2 in ['key1', 'key2', 'key3']
    
    def test_usage_tracking(self):
        """Test usage count tracking."""
        manager = WosApiKeyManager(['key1'])
        
        initial_usage = manager.get_usage_info()
        assert initial_usage['usage_count']['key1'] == 0
        
        # Increment usage
        manager.increment_usage('key1')
        updated_usage = manager.get_usage_info()
        assert updated_usage['usage_count']['key1'] == 1
    
    def test_daily_limit_enforcement(self):
        """Test daily limit enforcement."""
        manager = WosApiKeyManager(['key1'])
        manager.daily_limit = 2  # Set low limit for testing
        
        # Use up the daily limit
        for _ in range(2):
            key = manager.get_next_available_key()
            manager.increment_usage(key)
        
        # Should raise error when limit is reached
        with pytest.raises(ValueError, match="All WOS API keys have reached daily limit"):
            manager.get_next_available_key()
    
    def test_usage_reset(self):
        """Test usage count reset functionality."""
        manager = WosApiKeyManager(['key1'])
        
        # Increment usage
        manager.increment_usage('key1')
        assert manager.get_usage_info()['usage_count']['key1'] == 1
        
        # Reset usage
        manager.reset_usage()
        assert manager.get_usage_info()['usage_count']['key1'] == 0


if __name__ == '__main__':
    pytest.main([__file__])