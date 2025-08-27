"""
Unit tests for BaseSearchEngine abstract base class.

This module contains comprehensive tests for the BaseSearchEngine class,
including parameter validation, error handling, logging, and abstract method enforcement.
"""

import logging
from datetime import datetime
from typing import Dict, List, Tuple
from unittest.mock import patch

import pytest

from src.search.engine.base_engine import (
    BaseSearchEngine,
    SearchError,
    ParameterValidationError,
    NetworkError,
    FormatError
)


class ConcreteSearchEngine(BaseSearchEngine):
    """Concrete implementation of BaseSearchEngine for testing."""
    
    def __init__(self, source_name: str = "test_source"):
        self._source_name = source_name
        super().__init__()
    
    def get_source_name(self) -> str:
        return self._source_name
    
    def _search(self, query: str, **kwargs) -> Tuple[List[Dict], Dict]:
        """Mock implementation that returns test data."""
        raw_results = [
            {"title": "Test Article 1", "id": "1"},
            {"title": "Test Article 2", "id": "2"}
        ]
        metadata = {
            "total_count": 2,
            "query_time": 0.5
        }
        return raw_results, metadata
    
    def _response_format(self, results: List[Dict]) -> List[Dict]:
        """Mock implementation that formats results."""
        formatted_results = []
        for result in results:
            formatted_results.append({
                "article": {
                    "title": result.get("title", ""),
                    "primary_doi": None
                },
                "source_specific": {
                    "source": self.get_source_name(),
                    "raw_data": result
                }
            })
        return formatted_results


class FailingSearchEngine(BaseSearchEngine):
    """Search engine that fails for testing error handling."""
    
    def get_source_name(self) -> str:
        return "failing_source"
    
    def _search(self, query: str, **kwargs) -> Tuple[List[Dict], Dict]:
        raise NetworkError("Simulated network failure")
    
    def _response_format(self, results: List[Dict]) -> List[Dict]:
        raise FormatError("Simulated formatting failure")


class TestBaseSearchEngine:
    """Test cases for BaseSearchEngine class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = ConcreteSearchEngine()
        self.failing_engine = FailingSearchEngine()
    
    def test_abstract_class_cannot_be_instantiated(self):
        """Test that BaseSearchEngine cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseSearchEngine()
    
    def test_concrete_class_initialization(self):
        """Test that concrete implementation initializes correctly."""
        engine = ConcreteSearchEngine("test_source")
        
        assert engine.source_name == "test_source"
        assert engine.max_results_limit == 10000
        assert engine.default_results == 50
        assert engine.max_retry == 5
        assert hasattr(engine, 'logger')
    
    def test_get_source_name_abstract_method(self):
        """Test that get_source_name is properly implemented."""
        assert self.engine.get_source_name() == "test_source"
    
    def test_successful_search(self):
        """Test successful search execution."""
        query = "test query"
        results, metadata = self.engine.search(query, num_results=10)
        
        # Verify results structure
        assert isinstance(results, list)
        assert len(results) == 2
        assert isinstance(metadata, dict)
        
        # Verify formatted results
        for result in results:
            assert "article" in result
            assert "source_specific" in result
            assert result["source_specific"]["source"] == "test_source"
        
        # Verify metadata
        assert metadata["source"] == "test_source"
        assert metadata["formatted_count"] == 2
        assert metadata["raw_count"] == 2
        assert "search_duration_seconds" in metadata
        assert "timestamp" in metadata
        assert metadata["query"] == query
    
    def test_parameter_validation_valid_params(self):
        """Test parameter validation with valid parameters."""
        # Valid basic parameters
        assert self.engine.validate_params("test query") is True
        assert self.engine.validate_params("test query", num_results=100) is True
        assert self.engine.validate_params("test query", year="2020") is True
        assert self.engine.validate_params("test query", year="2020-2023") is True
        assert self.engine.validate_params("test query", sort="relevance") is True
        assert self.engine.validate_params("test query", field="title") is True
    
    def test_parameter_validation_invalid_query(self):
        """Test parameter validation with invalid queries."""
        # Empty or None queries
        assert self.engine.validate_params("") is False
        assert self.engine.validate_params("   ") is False
        assert self.engine.validate_params(None) is False
        assert self.engine.validate_params(123) is False
    
    def test_parameter_validation_invalid_num_results(self):
        """Test parameter validation with invalid num_results."""
        # Invalid num_results
        assert self.engine.validate_params("test", num_results=0) is False
        assert self.engine.validate_params("test", num_results=-1) is False
        assert self.engine.validate_params("test", num_results=20000) is False
        assert self.engine.validate_params("test", num_results="invalid") is False
    
    def test_parameter_validation_num_results_conversion(self):
        """Test that string num_results can be converted to int."""
        assert self.engine.validate_params("test", num_results="100") is True
        assert self.engine.validate_params("test", num_results="0") is False
    
    def test_parameter_validation_invalid_year(self):
        """Test parameter validation with invalid year formats."""
        # Invalid year formats
        assert self.engine.validate_params("test", year="invalid") is False
        assert self.engine.validate_params("test", year="20200") is False
        assert self.engine.validate_params("test", year="2020-2019") is False  # start > end
        assert self.engine.validate_params("test", year="800") is False  # too old
        assert self.engine.validate_params("test", year="3000") is False  # too future
        assert self.engine.validate_params("test", year=2020) is False  # not string
    
    def test_year_format_validation(self):
        """Test specific year format validation."""
        # Valid formats
        assert self.engine._validate_year_format("2020") is True
        assert self.engine._validate_year_format("2020-2023") is True
        assert self.engine._validate_year_format("2020-") is True
        assert self.engine._validate_year_format("-2023") is True
        
        # Invalid formats
        assert self.engine._validate_year_format("") is False
        assert self.engine._validate_year_format("   ") is False
        assert self.engine._validate_year_format("invalid") is False
        assert self.engine._validate_year_format("2020-2019") is False
        assert self.engine._validate_year_format("800") is False
        assert self.engine._validate_year_format("3000") is False
    
    def test_parameter_validation_invalid_types(self):
        """Test parameter validation with invalid parameter types."""
        assert self.engine.validate_params("test", sort=123) is False
        assert self.engine.validate_params("test", field=123) is False
    
    def test_search_with_invalid_parameters(self):
        """Test that search raises ParameterValidationError for invalid parameters."""
        with pytest.raises(ParameterValidationError):
            self.engine.search("")
        
        with pytest.raises(ParameterValidationError):
            self.engine.search("test", num_results=-1)
    
    def test_search_with_network_error(self):
        """Test that network errors are properly handled."""
        with pytest.raises(NetworkError):
            self.failing_engine.search("test query")
    
    def test_search_with_format_error(self):
        """Test that format errors are properly handled."""
        # Create an engine that fails during formatting
        class FormatFailingEngine(ConcreteSearchEngine):
            def _response_format(self, results: List[Dict]) -> List[Dict]:
                raise Exception("Formatting failed")
        
        engine = FormatFailingEngine()
        with pytest.raises(FormatError):
            engine.search("test query")
    
    def test_search_with_unexpected_error(self):
        """Test that unexpected errors are wrapped in SearchError."""
        # Create an engine that raises unexpected error
        class UnexpectedErrorEngine(ConcreteSearchEngine):
            def _search(self, query: str, **kwargs) -> Tuple[List[Dict], Dict]:
                raise ValueError("Unexpected error")
        
        engine = UnexpectedErrorEngine()
        with pytest.raises(SearchError):
            engine.search("test query")
    
    @patch('src.search.base_engine.datetime')
    def test_search_timing_metadata(self, mock_datetime):
        """Test that search timing is properly recorded in metadata."""
        # Mock datetime to control timing
        start_time = datetime(2023, 1, 1, 12, 0, 0)
        end_time = datetime(2023, 1, 1, 12, 0, 2)  # 2 seconds later
        
        mock_datetime.now.side_effect = [start_time, end_time, end_time]
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        
        results, metadata = self.engine.search("test query")
        
        assert metadata["search_duration_seconds"] == 2.0
        assert metadata["timestamp"] == end_time.isoformat()
    
    def test_get_search_stats(self):
        """Test get_search_stats method."""
        stats = self.engine.get_search_stats()
        
        expected_keys = [
            'source_name', 'max_results_limit', 'default_results', 
            'max_retry', 'class_name'
        ]
        
        for key in expected_keys:
            assert key in stats
        
        assert stats['source_name'] == 'test_source'
        assert stats['max_results_limit'] == 10000
        assert stats['default_results'] == 50
        assert stats['class_name'] == 'ConcreteSearchEngine'
    
    def test_string_representations(self):
        """Test __str__ and __repr__ methods."""
        str_repr = str(self.engine)
        assert "ConcreteSearchEngine" in str_repr
        assert "test_source" in str_repr
        
        repr_str = repr(self.engine)
        assert "ConcreteSearchEngine" in repr_str
        assert "test_source" in repr_str
        assert "max_results=10000" in repr_str
        assert "default_results=50" in repr_str
    
    def test_logging_configuration(self):
        """Test that logging is properly configured."""
        # Verify logger is created
        assert hasattr(self.engine, 'logger')
        assert isinstance(self.engine.logger, logging.Logger)
        
        # Verify logger name
        expected_name = f"src.search.base_engine.ConcreteSearchEngine"
        assert self.engine.logger.name == expected_name
    
    def test_search_logging(self):
        """Test that search operations are properly logged."""
        with patch.object(self.engine.logger, 'info') as mock_info, \
             patch.object(self.engine.logger, 'debug') as mock_debug:
            
            self.engine.search("test query")
            
            # Verify info logging calls
            mock_info.assert_called()
            
            # Check that search initiation and completion are logged
            info_calls = [call.args[0] for call in mock_info.call_args_list]
            assert any("Starting search" in call for call in info_calls)
            assert any("Search completed successfully" in call for call in info_calls)
    
    def test_metadata_completeness(self):
        """Test that all expected metadata fields are present."""
        query = "test query"
        params = {"num_results": 10, "year": "2020"}
        
        results, metadata = self.engine.search(query, **params)
        
        expected_fields = [
            'source', 'formatted_count', 'raw_count', 'search_duration_seconds',
            'timestamp', 'query', 'parameters', 'total_count', 'query_time'
        ]
        
        for field in expected_fields:
            assert field in metadata, f"Missing metadata field: {field}"
        
        assert metadata['query'] == query
        assert metadata['parameters'] == params
    
    def test_abstract_methods_enforcement(self):
        """Test that abstract methods must be implemented."""
        # Create a class that doesn't implement all abstract methods
        with pytest.raises(TypeError):
            class IncompleteEngine(BaseSearchEngine):
                def get_source_name(self) -> str:
                    return "incomplete"
                # Missing _search and _response_format
            
            IncompleteEngine()
    
    def test_custom_validation_override(self):
        """Test that subclasses can override validation logic."""
        class CustomValidationEngine(ConcreteSearchEngine):
            def validate_params(self, query: str, **kwargs) -> bool:
                # Custom validation that requires specific field
                if not kwargs.get('required_field'):
                    return False
                return super().validate_params(query, **kwargs)
        
        engine = CustomValidationEngine()
        
        # Should fail without required_field
        assert engine.validate_params("test") is False
        
        # Should pass with required_field
        assert engine.validate_params("test", required_field="value") is True


class TestSearchExceptions:
    """Test cases for search exception classes."""
    
    def test_search_error_hierarchy(self):
        """Test that all search exceptions inherit from SearchError."""
        assert issubclass(ParameterValidationError, SearchError)
        assert issubclass(NetworkError, SearchError)
        assert issubclass(FormatError, SearchError)
    
    def test_exception_instantiation(self):
        """Test that exceptions can be instantiated with messages."""
        msg = "Test error message"
        
        search_error = SearchError(msg)
        param_error = ParameterValidationError(msg)
        network_error = NetworkError(msg)
        format_error = FormatError(msg)
        
        assert str(search_error) == msg
        assert str(param_error) == msg
        assert str(network_error) == msg
        assert str(format_error) == msg


if __name__ == "__main__":
    pytest.main([__file__])