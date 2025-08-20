#!/usr/bin/env python3
"""
Integration test for the refactored PubMed API.
This script tests the refactored PubMed API to ensure it works correctly.
"""

from src.search.pubmed_search import PubmedSearchAPI
from src.models.schemas import LiteratureSchema
import json

def test_pubmed_integration():
    """Test the refactored PubMed API integration."""
    print("Testing refactored PubMed API...")
    
    # Initialize the API
    api = PubmedSearchAPI()
    print(f"✓ API initialized: {api}")
    print(f"✓ Source name: {api.get_source_name()}")
    
    # Test parameter validation
    print("\nTesting parameter validation...")
    assert api.validate_params("test query"), "Basic validation failed"
    assert api.validate_params("test", num_results=100), "Num results validation failed"
    assert not api.validate_params(""), "Empty query should fail"
    assert not api.validate_params("test", num_results=0), "Zero results should fail"
    print("✓ Parameter validation works correctly")
    
    # Test with mock data (since we don't want to make real API calls in tests)
    print("\nTesting response formatting...")
    
    # Sample raw PubMed result
    sample_raw_result = {
        'pmid': '12345678',
        'title': 'Test Article: Machine Learning in Healthcare',
        'abstract': 'This study explores the application of machine learning techniques in healthcare diagnostics.',
        'authors': ['Smith, John A.', 'Doe, Jane B.', 'Johnson, Robert C.'],
        'journal': 'Journal of Medical Informatics',
        'issn': '1234-5678',
        'eissn': '8765-4321',
        'volume': '45',
        'issue': '3',
        'doi': '10.1234/jmi.2023.12345',
        'published_date': '2023-03-15',
        'year': 2023
    }
    
    # Test response formatting
    formatted_results = api._response_format([sample_raw_result], 'pubmed')
    
    assert len(formatted_results) == 1, "Should format one result"
    result = formatted_results[0]
    
    # Verify structure
    required_keys = ['article', 'authors', 'venue', 'publication', 'identifiers', 'source_specific']
    for key in required_keys:
        assert key in result, f"Missing key: {key}"
    
    # Verify article data
    article = result['article']
    assert article['title'] == 'Test Article: Machine Learning in Healthcare'
    assert article['primary_doi'] == '10.1234/jmi.2023.12345'
    assert article['publication_year'] == 2023
    
    # Verify authors
    authors = result['authors']
    assert len(authors) == 3
    assert authors[0]['full_name'] == 'Smith, John A.'
    
    # Verify venue
    venue = result['venue']
    assert venue['venue_name'] == 'Journal of Medical Informatics'
    assert venue['venue_type'] == 'journal'
    
    # Verify identifiers
    identifiers = result['identifiers']
    doi_found = any(id['identifier_type'] == 'doi' for id in identifiers)
    pmid_found = any(id['identifier_type'] == 'pmid' for id in identifiers)
    assert doi_found, "DOI identifier not found"
    assert pmid_found, "PMID identifier not found"
    
    print("✓ Response formatting works correctly")
    
    # Test schema validation
    print("\nTesting schema validation...")
    literature = LiteratureSchema.from_dict(result)
    is_valid, errors = literature.validate()
    assert is_valid, f"Schema validation failed: {errors}"
    print("✓ Schema validation passes")
    
    # Test backward compatibility
    print("\nTesting backward compatibility...")
    
    # Mock the internal query method for testing
    original_query = api.query
    def mock_query(*args, **kwargs):
        return [sample_raw_result], {'count': 1, 'query': 'test'}
    
    api.query = mock_query
    
    try:
        # Test legacy search method
        legacy_results, metadata = api.search_legacy('test query')
        assert len(legacy_results) == 1
        assert legacy_results[0] == sample_raw_result
        print("✓ Legacy search method works")
        
        # Test new search method
        new_results, new_metadata = api.search('test query')
        assert len(new_results) == 1
        assert 'article' in new_results[0]
        assert new_metadata['source'] == 'pubmed'
        print("✓ New search method works")
        
    finally:
        # Restore original method
        api.query = original_query
    
    print("\n✅ All integration tests passed!")
    print("The refactored PubMed API is working correctly and maintains backward compatibility.")

if __name__ == '__main__':
    test_pubmed_integration()