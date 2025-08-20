"""
Example demonstrating the BaseSearchEngine abstract base class.

This example shows how to create a concrete implementation of BaseSearchEngine
and demonstrates its key features including parameter validation, error handling,
and result formatting.
"""

from typing import Dict, List, Tuple
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.search.base_engine import BaseSearchEngine, ParameterValidationError, NetworkError


class ExampleSearchEngine(BaseSearchEngine):
    """
    Example concrete implementation of BaseSearchEngine.
    
    This is a mock search engine that demonstrates how to implement
    the abstract methods required by BaseSearchEngine.
    """
    
    def get_source_name(self) -> str:
        """Return the name of this search engine."""
        return "example_source"
    
    def _search(self, query: str, **kwargs) -> Tuple[List[Dict], Dict]:
        """
        Mock implementation of raw search.
        
        In a real implementation, this would make API calls to the actual
        search service and return raw results.
        """
        # Simulate some search parameters
        num_results = kwargs.get('num_results', self.default_results)
        year = kwargs.get('year', '')
        
        # Mock raw results that might come from an API
        raw_results = []
        for i in range(min(num_results, 5)):  # Limit to 5 for demo
            raw_results.append({
                'id': f'example_{i+1}',
                'title': f'Example Article {i+1}: {query}',
                'abstract': f'This is a mock abstract for article {i+1} about {query}.',
                'authors': [f'Author {i+1}A', f'Author {i+1}B'],
                'year': 2023 - i,
                'doi': f'10.1000/example.{i+1}',
                'journal': 'Example Journal',
                'volume': str(10 + i),
                'issue': str(i + 1)
            })
        
        # Mock metadata that might come from an API
        metadata = {
            'total_found': len(raw_results),
            'query_time': 0.123,
            'api_version': '1.0',
            'search_params': {
                'query': query,
                'year': year,
                'num_results': num_results
            }
        }
        
        return raw_results, metadata
    
    def _response_format(self, results: List[Dict], source: str) -> List[Dict]:
        """
        Format raw results into standardized LiteratureSchema format.
        
        This method converts the raw API response into the unified format
        expected by the literature aggregation system.
        """
        formatted_results = []
        
        for result in results:
            # Format according to LiteratureSchema structure
            formatted_result = {
                'article': {
                    'primary_doi': result.get('doi'),
                    'title': result.get('title', ''),
                    'abstract': result.get('abstract'),
                    'publication_year': result.get('year'),
                    'citation_count': 0,  # Not available in this mock
                    'is_open_access': False  # Not available in this mock
                },
                'authors': [
                    {'full_name': author, 'author_order': i+1} 
                    for i, author in enumerate(result.get('authors', []))
                ],
                'venue': {
                    'venue_name': result.get('journal', ''),
                    'venue_type': 'journal'
                },
                'publication': {
                    'volume': result.get('volume'),
                    'issue': result.get('issue')
                },
                'identifiers': [
                    {
                        'identifier_type': 'doi',
                        'identifier_value': result.get('doi'),
                        'is_primary': True
                    }
                ],
                'source_specific': {
                    'source': source,
                    'raw_data': result
                }
            }
            formatted_results.append(formatted_result)
        
        return formatted_results


def demonstrate_basic_usage():
    """Demonstrate basic usage of the search engine."""
    print("=== Basic Usage Example ===")
    
    # Create an instance of our example search engine
    engine = ExampleSearchEngine()
    
    # Perform a basic search
    query = "machine learning"
    results, metadata = engine.search(query, num_results=3)
    
    print(f"Search query: '{query}'")
    print(f"Found {len(results)} results")
    print(f"Search took {metadata['search_duration_seconds']:.3f} seconds")
    print()
    
    # Display first result
    if results:
        first_result = results[0]
        print("First result:")
        print(f"  Title: {first_result['article']['title']}")
        print(f"  DOI: {first_result['article']['primary_doi']}")
        print(f"  Authors: {[a['full_name'] for a in first_result['authors']]}")
        print(f"  Journal: {first_result['venue']['venue_name']}")
    print()


def demonstrate_parameter_validation():
    """Demonstrate parameter validation features."""
    print("=== Parameter Validation Example ===")
    
    engine = ExampleSearchEngine()
    
    # Valid parameters
    try:
        results, metadata = engine.search("valid query", num_results=10, year="2020-2023")
        print("✓ Valid parameters accepted")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
    
    # Invalid parameters
    invalid_cases = [
        ("", {}),  # Empty query
        ("test", {"num_results": -1}),  # Negative num_results
        ("test", {"num_results": 20000}),  # Too many results
        ("test", {"year": "invalid"}),  # Invalid year format
    ]
    
    for query, params in invalid_cases:
        try:
            engine.search(query, **params)
            print(f"✗ Should have failed: query='{query}', params={params}")
        except ParameterValidationError:
            print(f"✓ Correctly rejected invalid params: query='{query}', params={params}")
        except Exception as e:
            print(f"✗ Unexpected error type: {e}")
    print()


def demonstrate_error_handling():
    """Demonstrate error handling capabilities."""
    print("=== Error Handling Example ===")
    
    class FailingSearchEngine(ExampleSearchEngine):
        """Search engine that fails to demonstrate error handling."""
        
        def _search(self, query: str, **kwargs) -> Tuple[List[Dict], Dict]:
            if "network_error" in query:
                raise NetworkError("Simulated network failure")
            return super()._search(query, **kwargs)
    
    engine = FailingSearchEngine()
    
    # Test network error handling
    try:
        engine.search("network_error test")
        print("✗ Should have raised NetworkError")
    except NetworkError as e:
        print(f"✓ Correctly handled NetworkError: {e}")
    except Exception as e:
        print(f"✗ Unexpected error type: {e}")
    print()


def demonstrate_metadata():
    """Demonstrate metadata collection."""
    print("=== Metadata Example ===")
    
    engine = ExampleSearchEngine()
    results, metadata = engine.search("artificial intelligence", num_results=2, year="2022")
    
    print("Metadata collected:")
    for key, value in metadata.items():
        if key == 'parameters':
            print(f"  {key}: {value}")
        elif key == 'search_params':
            print(f"  {key}: {value}")
        else:
            print(f"  {key}: {value}")
    print()


def demonstrate_engine_stats():
    """Demonstrate engine statistics."""
    print("=== Engine Statistics Example ===")
    
    engine = ExampleSearchEngine()
    stats = engine.get_search_stats()
    
    print("Engine statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print(f"\nString representation: {engine}")
    print(f"Detailed representation: {repr(engine)}")
    print()


if __name__ == "__main__":
    print("BaseSearchEngine Example")
    print("=" * 50)
    print()
    
    demonstrate_basic_usage()
    demonstrate_parameter_validation()
    demonstrate_error_handling()
    demonstrate_metadata()
    demonstrate_engine_stats()
    
    print("Example completed successfully!")