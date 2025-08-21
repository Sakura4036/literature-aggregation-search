"""
BaseSearchEngine - Abstract base class for all literature search engines.

This module provides the unified interface and common functionality for all
literature search APIs, ensuring consistency and standardization across
different data sources.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Any, Optional, Union
from datetime import datetime

# Configure logger
logger = logging.getLogger(__name__)


class SearchError(Exception):
    """Base exception class for search-related errors."""
    pass


class ParameterValidationError(SearchError):
    """Exception raised when search parameters are invalid."""
    pass


class NetworkError(SearchError):
    """Exception raised when network requests fail."""
    pass


class FormatError(SearchError):
    """Exception raised when data formatting fails."""
    pass


class BaseSearchEngine(ABC):
    """
    Abstract base class for literature search engines.
    
    This class defines the unified interface that all search engines must implement,
    providing common functionality for parameter validation, error handling, and
    result formatting.
    
    All concrete search engine implementations must inherit from this class and
    implement the abstract methods: _search(), _response_format(), and get_source_name().
    """
    
    def __init__(self):
        """Initialize the base search engine."""
        self.source_name = self.get_source_name()
        self.max_results_limit = 10000
        self.default_results = 50
        self.max_retry = 5
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Log initialization
        self.logger.debug(f"Initialized {self.__class__.__name__} search engine")
    
    def search(self, query: str, **kwargs) -> Tuple[List[Dict], Dict]:
        """
        Public search interface - unified entry point for all search APIs.
        
        This method provides the main interface for searching literature. It handles
        parameter validation, executes the search, formats results, and manages
        error handling and logging.
        
        Args:
            query (str): Search query string
            **kwargs: Additional search parameters such as:
                - num_results (int): Number of results to return (default: 50, max: 10000)
                - year (str): Year range filter (e.g., '2020-2023')
                - field (str): Specific field to search in
                - sort (str): Sort order for results
                
        Returns:
            Tuple[List[Dict], Dict]: A tuple containing:
                - List of formatted search results conforming to LiteratureSchema
                - Metadata dictionary with search information
                
        Raises:
            ParameterValidationError: If input parameters are invalid
            NetworkError: If network requests fail
            FormatError: If result formatting fails
            SearchError: For other search-related errors
        """
        start_time = datetime.now()
        
        try:
            # Log search initiation
            self.logger.info(f"Starting search with query: '{query}' on source: {self.source_name}")
            
            # 1. Parameter validation
            if not self.validate_params(query, **kwargs):
                error_msg = f"Invalid parameters for query: '{query}'"
                self.logger.error(error_msg)
                raise ParameterValidationError(error_msg)
            
            # 2. Execute raw search
            self.logger.debug("Executing raw search...")
            raw_results, metadata = self._search(query, **kwargs)
            
            # 3. Format results
            self.logger.debug(f"Formatting {len(raw_results)} raw results...")
            try:
                formatted_results = self._response_format(raw_results)
            except Exception as e:
                self.logger.error(f"Error formatting results: {e}")
                raise FormatError(f"Failed to format search results: {e}")
            
            # 4. Update metadata with additional information
            end_time = datetime.now()
            search_duration = (end_time - start_time).total_seconds()
            
            metadata.update({
                'source': self.source_name,
                'formatted_count': len(formatted_results),
                'raw_count': len(raw_results),
                'search_duration_seconds': search_duration,
                'timestamp': end_time.isoformat(),
                'query': query,
                'parameters': kwargs
            })
            
            self.logger.info(
                f"Search completed successfully. "
                f"Raw results: {len(raw_results)}, "
                f"Formatted results: {len(formatted_results)}, "
                f"Duration: {search_duration:.2f}s"
            )
            
            return formatted_results, metadata
            
        except (ParameterValidationError, NetworkError, FormatError):
            # Re-raise known exceptions
            raise
        except Exception as e:
            # Log and wrap unexpected exceptions
            error_msg = f"Unexpected error during search: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise SearchError(error_msg) from e
    
    @abstractmethod
    def _search(self, query: str, **kwargs) -> Tuple[List[Dict], Dict]:
        """
        Execute raw search against the specific data source.
        
        This method must be implemented by each concrete search engine to perform
        the actual search operation against their respective APIs.
        
        Args:
            query (str): Search query string
            **kwargs: Search parameters specific to the data source
            
        Returns:
            Tuple[List[Dict], Dict]: A tuple containing:
                - List of raw search results from the API
                - Metadata dictionary with search information
                
        Raises:
            NetworkError: If the API request fails
            SearchError: For other search-related errors
        """
        pass
    
    @abstractmethod
    def _response_format(self, results: List[Dict]) -> List[Dict]:
        """
        Format raw search results into standardized LiteratureSchema format.
        
        This method must be implemented by each concrete search engine to convert
        their API's raw response format into the unified LiteratureSchema format.
        
        Args:
            results (List[Dict]): Raw search results from the API
            
        Returns:
            List[Dict]: List of formatted results conforming to LiteratureSchema
            
        Raises:
            FormatError: If formatting fails
        """
        pass
    
    @abstractmethod
    def get_source_name(self) -> str:
        """
        Get the name of the data source.
        
        Returns:
            str: Name of the data source (e.g., 'pubmed', 'arxiv', 'semantic_scholar')
        """
        pass
    
    def validate_params(self, query: str, **kwargs) -> bool:
        """
        Validate search parameters.
        
        This method provides basic parameter validation that can be extended
        by subclasses for source-specific validation requirements.
        
        Args:
            query (str): Search query string
            **kwargs: Additional search parameters
            
        Returns:
            bool: True if parameters are valid, False otherwise
        """
        try:
            # Validate query
            if not query or not isinstance(query, str) or not query.strip():
                self.logger.error("Query must be a non-empty string")
                return False
            
            # Validate num_results
            num_results = kwargs.get('num_results', self.default_results)
            if not isinstance(num_results, int):
                try:
                    num_results = int(num_results)
                except (ValueError, TypeError):
                    self.logger.error(f"num_results must be an integer, got: {type(num_results)}")
                    return False
            
            if num_results <= 0:
                self.logger.error(f"num_results must be positive, got: {num_results}")
                return False
                
            if num_results > self.max_results_limit:
                self.logger.error(
                    f"num_results exceeds maximum limit of {self.max_results_limit}, got: {num_results}"
                )
                return False
            
            # Validate year parameter if provided
            year = kwargs.get('year')
            if year is not None:
                if not isinstance(year, str):
                    self.logger.error(f"year must be a string, got: {type(year)}")
                    return False
                
                if not self._validate_year_format(year):
                    self.logger.error(f"Invalid year format: {year}")
                    return False
            
            # Validate sort parameter if provided
            sort = kwargs.get('sort')
            if sort is not None and not isinstance(sort, str):
                self.logger.error(f"sort must be a string, got: {type(sort)}")
                return False
            
            # Validate field parameter if provided
            field = kwargs.get('field')
            if field is not None and not isinstance(field, str):
                self.logger.error(f"field must be a string, got: {type(field)}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error during parameter validation: {e}")
            return False
    
    def _validate_year_format(self, year: str) -> bool:
        """
        Validate year format.
        
        Accepts formats like: '2020', '2020-2023', '2020-', '-2023'
        
        Args:
            year (str): Year string to validate
            
        Returns:
            bool: True if format is valid, False otherwise
        """
        if not year.strip():
            return False
        
        try:
            current_year = datetime.now().year
            
            # Handle different year formats
            if year.startswith('-'):
                # Format: '-2023'
                end_year = int(year[1:])
                return 1000 <= end_year <= current_year + 5
                
            elif year.endswith('-'):
                # Format: '2020-'
                start_year = int(year[:-1])
                return 1000 <= start_year <= current_year + 5
                
            elif '-' in year:
                # Format: '2020-2023'
                start_year_str, end_year_str = year.split('-', 1)
                start_year = int(start_year_str)
                end_year = int(end_year_str)
                return (1000 <= start_year <= current_year + 5 and 
                       1000 <= end_year <= current_year + 5 and 
                       start_year <= end_year)
            else:
                # Format: '2020'
                single_year = int(year)
                return 1000 <= single_year <= current_year + 5
                
        except ValueError:
            return False
    
    def get_search_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the search engine.
        
        Returns:
            Dict[str, Any]: Dictionary containing search engine statistics
        """
        return {
            'source_name': self.source_name,
            'max_results_limit': self.max_results_limit,
            'default_results': self.default_results,
            'max_retry': self.max_retry,
            'class_name': self.__class__.__name__
        }
    
    def __str__(self) -> str:
        """String representation of the search engine."""
        return f"{self.__class__.__name__}(source='{self.source_name}')"
    
    def __repr__(self) -> str:
        """Detailed string representation of the search engine."""
        return (f"{self.__class__.__name__}("
                f"source='{self.source_name}', "
                f"max_results={self.max_results_limit}, "
                f"default_results={self.default_results})")