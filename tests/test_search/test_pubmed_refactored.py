"""
Tests for the refactored PubMed search API.

This module tests the PubmedSearchAPI class to ensure it properly implements
the BaseSearchEngine interface and correctly formats results into LiteratureSchema.
"""

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.search.pubmed_search import PubmedSearchAPI
from src.search.base_engine import BaseSearchEngine, ParameterValidationError, NetworkError, FormatError
from src.models.schemas import LiteratureSchema, ArticleSchema, AuthorSchema, VenueSchema
from src.models.enums import IdentifierType, VenueType


class TestPubmedSearchAPIRefactored(unittest.TestCase):
    """Test cases for the refactored PubMed search API."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.api = PubmedSearchAPI()
        
        # Sample raw PubMed result
        self.sample_raw_result = {
            'pmid': '12345678',
            'title': 'Sample Research Article',
            'abstract': 'This is a sample abstract for testing purposes.',
            'authors': ['John Doe', 'Jane Smith'],
            'journal': 'Nature',
            'issn': '0028-0836',
            'eissn': '1476-4687',
            'volume': '123',
            'issue': '4567',
            'doi': '10.1038/nature12345',
            'published_date': '2023-01-15',
            'year': 2023
        }
        
        # Sample search metadata
        self.sample_metadata = {
            'count': 1,
            'webenv': 'test_webenv',
            'querykey': 'test_querykey',
            'retstart': 0,
            'retmax': 20,
            'idlist': ['12345678'],
            'url': 'https://test.url',
            'query': 'test query'
        }
    
    def test_inheritance(self):
        """Test that PubmedSearchAPI properly inherits from BaseSearchEngine."""
        self.assertIsInstance(self.api, BaseSearchEngine)
        self.assertTrue(hasattr(self.api, 'search'))
        self.assertTrue(hasattr(self.api, '_search'))
        self.assertTrue(hasattr(self.api, '_response_format'))
        self.assertTrue(hasattr(self.api, 'get_source_name'))
    
    def test_get_source_name(self):
        """Test that get_source_name returns correct value."""
        self.assertEqual(self.api.get_source_name(), 'pubmed')
        self.assertEqual(self.api.source_name, 'pubmed')
    
    def test_initialization(self):
        """Test proper initialization of PubMed API."""
        self.assertEqual(self.api.source_name, 'pubmed')
        self.assertEqual(self.api.max_results_limit, 10000)
        self.assertEqual(self.api.default_results, 50)
        self.assertIsNotNone(self.api.pubmed_search_url)
        self.assertIsNotNone(self.api.pubmed_fetch_url)
    
    def test_validate_params_basic(self):
        """Test basic parameter validation."""
        # Valid parameters
        self.assertTrue(self.api.validate_params('test query'))
        self.assertTrue(self.api.validate_params('test query', num_results=100))
        self.assertTrue(self.api.validate_params('test query', year='2020-2023'))
        
        # Invalid parameters
        self.assertFalse(self.api.validate_params(''))  # Empty query
        self.assertFalse(self.api.validate_params('test', num_results=0))  # Invalid num_results
        self.assertFalse(self.api.validate_params('test', num_results=20000))  # Exceeds limit
    
    def test_validate_params_pubmed_specific(self):
        """Test PubMed-specific parameter validation."""
        # Valid sort parameters
        self.assertTrue(self.api.validate_params('test', sort='relevance'))
        self.assertTrue(self.api.validate_params('test', sort='pub_date'))
        self.assertTrue(self.api.validate_params('test', sort='Author'))
        self.assertTrue(self.api.validate_params('test', sort='JournalName'))
        
        # Invalid sort parameter
        self.assertFalse(self.api.validate_params('test', sort='invalid_sort'))
        
        # Field parameters (should accept various formats)
        self.assertTrue(self.api.validate_params('test', field='[Title]'))
        self.assertTrue(self.api.validate_params('test', field='Title'))  # Backward compatibility
    
    @patch.object(PubmedSearchAPI, 'query')
    def test_search_method(self, mock_query):
        """Test the _search method."""
        # Mock the query method
        mock_query.return_value = ([self.sample_raw_result], self.sample_metadata)
        
        # Test _search method
        results, metadata = self.api._search('test query', num_results=20)
        
        # Verify query was called with correct parameters
        mock_query.assert_called_once_with(
            query='test query',
            year='',
            field='',
            sort='relevance',
            num_results=20
        )
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], self.sample_raw_result)
        self.assertEqual(metadata, self.sample_metadata)
    
    def test_response_format_method(self):
        """Test the _response_format method."""
        raw_results = [self.sample_raw_result]
        
        formatted_results = self.api._response_format(raw_results, 'pubmed')
        
        # Verify formatting
        self.assertEqual(len(formatted_results), 1)
        result = formatted_results[0]
        
        # Check structure
        self.assertIn('article', result)
        self.assertIn('authors', result)
        self.assertIn('venue', result)
        self.assertIn('publication', result)
        self.assertIn('identifiers', result)
        self.assertIn('source_specific', result)
        
        # Check article data
        article = result['article']
        self.assertEqual(article['title'], 'Sample Research Article')
        self.assertEqual(article['abstract'], 'This is a sample abstract for testing purposes.')
        self.assertEqual(article['primary_doi'], '10.1038/nature12345')
        self.assertEqual(article['publication_year'], 2023)
        
        # Check authors
        authors = result['authors']
        self.assertEqual(len(authors), 2)
        self.assertEqual(authors[0]['full_name'], 'John Doe')
        self.assertEqual(authors[1]['full_name'], 'Jane Smith')
        
        # Check venue
        venue = result['venue']
        self.assertEqual(venue['venue_name'], 'Nature')
        self.assertEqual(venue['venue_type'], VenueType.JOURNAL.value)
        self.assertEqual(venue['issn_print'], '0028-0836')
        
        # Check identifiers
        identifiers = result['identifiers']
        self.assertTrue(len(identifiers) >= 2)  # Should have DOI and PMID
        
        # Find DOI and PMID identifiers
        doi_identifier = next((id for id in identifiers if id['identifier_type'] == IdentifierType.DOI.value), None)
        pmid_identifier = next((id for id in identifiers if id['identifier_type'] == IdentifierType.PMID.value), None)
        
        self.assertIsNotNone(doi_identifier)
        self.assertIsNotNone(pmid_identifier)
        self.assertEqual(doi_identifier['identifier_value'], '10.1038/nature12345')
        self.assertEqual(pmid_identifier['identifier_value'], '12345678')
        self.assertTrue(doi_identifier['is_primary'])
    
    def test_response_format_missing_fields(self):
        """Test response formatting with missing fields."""
        # Create result with minimal data
        minimal_result = {
            'pmid': '87654321',
            'title': 'Minimal Article',
            'authors': []
        }
        
        formatted_results = self.api._response_format([minimal_result], 'pubmed')
        
        self.assertEqual(len(formatted_results), 1)
        result = formatted_results[0]
        
        # Check that missing fields are handled gracefully
        self.assertEqual(result['article']['title'], 'Minimal Article')
        self.assertIsNone(result['article']['abstract'])
        self.assertIsNone(result['article']['primary_doi'])
        self.assertEqual(len(result['authors']), 0)
        
        # Should still have PMID identifier
        identifiers = result['identifiers']
        pmid_identifier = next((id for id in identifiers if id['identifier_type'] == IdentifierType.PMID.value), None)
        self.assertIsNotNone(pmid_identifier)
        self.assertEqual(pmid_identifier['identifier_value'], '87654321')
        self.assertTrue(pmid_identifier['is_primary'])  # Primary since no DOI
    
    def test_response_format_error_handling(self):
        """Test error handling in response formatting."""
        # Test with invalid data
        invalid_results = [{'invalid': 'data'}]
        
        # Should not raise exception but log warnings
        formatted_results = self.api._response_format(invalid_results, 'pubmed')
        
        # Should return empty list or handle gracefully
        self.assertIsInstance(formatted_results, list)
    
    @patch.object(PubmedSearchAPI, 'query')
    def test_full_search_integration(self, mock_query):
        """Test the full search method integration."""
        # Mock the query method
        mock_query.return_value = ([self.sample_raw_result], self.sample_metadata)
        
        # Test full search
        formatted_results, metadata = self.api.search('test query', num_results=20)
        
        # Verify results are formatted
        self.assertEqual(len(formatted_results), 1)
        self.assertIn('article', formatted_results[0])
        
        # Verify metadata is enhanced
        self.assertEqual(metadata['source'], 'pubmed')
        self.assertEqual(metadata['formatted_count'], 1)
        self.assertEqual(metadata['raw_count'], 1)
        self.assertIn('search_duration_seconds', metadata)
        self.assertIn('timestamp', metadata)
    
    def test_legacy_search_method(self):
        """Test the legacy search method for backward compatibility."""
        with patch.object(self.api, 'search') as mock_search:
            # Mock the new search method
            formatted_result = {
                'article': {'title': 'Test'},
                'source_specific': {'raw_data': self.sample_raw_result}
            }
            mock_search.return_value = ([formatted_result], self.sample_metadata)
            
            # Test legacy method
            legacy_results, metadata = self.api.search_legacy('test query')
            
            # Verify it calls the new search method
            mock_search.assert_called_once()
            
            # Verify it returns raw data format
            self.assertEqual(len(legacy_results), 1)
            self.assertEqual(legacy_results[0], self.sample_raw_result)
    
    def test_parameter_validation_error(self):
        """Test parameter validation error handling."""
        with self.assertRaises(ParameterValidationError):
            self.api.search('')  # Empty query should raise error
    
    @patch.object(PubmedSearchAPI, 'query')
    def test_network_error_handling(self, mock_query):
        """Test network error handling."""
        # Mock query to raise an exception
        mock_query.side_effect = Exception("Network error")
        
        with self.assertRaises(NetworkError):
            self.api._search('test query')
    
    def test_format_error_handling(self):
        """Test format error handling."""
        # This should be tested by mocking internal methods if needed
        # For now, we test that malformed data doesn't crash the formatter
        malformed_data = [None, {}, {'title': None}]
        
        try:
            result = self.api._response_format(malformed_data, 'pubmed')
            # Should handle gracefully
            self.assertIsInstance(result, list)
        except FormatError:
            # This is also acceptable behavior
            pass
    
    def test_schema_validation(self):
        """Test that formatted results pass schema validation."""
        formatted_results = self.api._response_format([self.sample_raw_result], 'pubmed')
        
        # Create LiteratureSchema from formatted result
        literature = LiteratureSchema.from_dict(formatted_results[0])
        
        # Validate schema
        is_valid, errors = literature.validate()
        self.assertTrue(is_valid, f"Schema validation failed: {errors}")
    
    def test_identifier_handling(self):
        """Test proper handling of different identifier types."""
        # Test with both DOI and PMID
        result_with_both = self.sample_raw_result.copy()
        formatted = self.api._response_format([result_with_both], 'pubmed')
        identifiers = formatted[0]['identifiers']
        
        # Should have both DOI and PMID
        doi_ids = [id for id in identifiers if id['identifier_type'] == IdentifierType.DOI.value]
        pmid_ids = [id for id in identifiers if id['identifier_type'] == IdentifierType.PMID.value]
        
        self.assertEqual(len(doi_ids), 1)
        self.assertEqual(len(pmid_ids), 1)
        self.assertTrue(doi_ids[0]['is_primary'])
        self.assertFalse(pmid_ids[0]['is_primary'])
        
        # Test with only PMID (no DOI)
        result_no_doi = self.sample_raw_result.copy()
        result_no_doi['doi'] = ''
        formatted_no_doi = self.api._response_format([result_no_doi], 'pubmed')
        identifiers_no_doi = formatted_no_doi[0]['identifiers']
        
        pmid_ids_no_doi = [id for id in identifiers_no_doi if id['identifier_type'] == IdentifierType.PMID.value]
        self.assertEqual(len(pmid_ids_no_doi), 1)
        self.assertTrue(pmid_ids_no_doi[0]['is_primary'])  # Should be primary when no DOI


if __name__ == '__main__':
    unittest.main()