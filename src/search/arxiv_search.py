import logging
import math
from typing import Generator, List, Dict, Tuple, Any
import arxiv
from urllib.parse import urlencode
from .utils import year_split
from .base_engine import BaseSearchEngine, NetworkError, FormatError
from ..models.schemas import LiteratureSchema, ArticleSchema, AuthorSchema, VenueSchema, IdentifierSchema, CategorySchema
from ..models.enums import IdentifierType, VenueType, CategoryType

logger = logging.getLogger(__name__)


def result_to_dict(result: arxiv.Result):
    return {
        'entry_id': result.entry_id,
        'updated': result.updated.isoformat(),
        'published': result.published.isoformat(),
        'title': result.title,
        'abstract': result.summary,
        'comment': result.comment,
        'authors': [author.name for author in result.authors],
        'doi': result.doi,
        'year': result.published.year,
        'url': result.entry_id,
        'arxiv_id': result.get_short_id(),
        'journal': result.journal_ref,
        'links': [{
            "href": link.href,
            "type": link.content_type,
            "title": link.title,
            'rel': link.rel,
        } for link in result.links],
        'categories': result.categories,
        'pdf_url': result.pdf_url,
    }


class ArxivSearch(arxiv.Search):
    """
    A specification for a search of arXiv's database.

    To run a search, use `Search.run` to use a default client or `Client.run`
    with a specific client.
    """

    query: str
    """
    A query string.

    This should be unencoded. Use `au:del_maestro AND ti:checkerboard`, not
    `au:del_maestro+AND+ti:checkerboard`.

    See [the arXiv API User's Manual: Details of Query
    Construction](https://arxiv.org/help/api/user-manual#query_details).
    """
    id_list: List[str]
    """
    A list of arXiv article IDs to which to limit the search.

    See [the arXiv API User's
    Manual](https://arxiv.org/help/api/user-manual#search_query_and_id_list)
    for documentation of the interaction between `query` and `id_list`.
    """
    max_results: int | None
    """
    The maximum number of results to be returned in an execution of this
    search. To fetch every result available, set `max_results=None`.

    The API's limit is 300,000 results per query.
    """
    sort_by: arxiv.SortCriterion
    """The sort criterion for results."""
    sort_order: arxiv.SortOrder
    """The sort order for results."""

    def __init__(
            self,
            query: str = "",
            id_list: List[str] = [],
            max_results: int | None = None,
            sort_by: arxiv.SortCriterion = arxiv.SortCriterion.Relevance,
            sort_order: arxiv.SortOrder = arxiv.SortOrder.Descending,
    ):
        """
        Constructs an arXiv API search with the specified criteria.
        """
        self.query = query
        self.id_list = id_list
        # Handle deprecated v1 default behavior.
        self.max_results = None if max_results == math.inf else max_results
        self.sort_by = sort_by
        self.sort_order = sort_order
        super().__init__(
            query=query,
            id_list=id_list,
            max_results=max_results,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def _url_args(self) -> Dict[str, str]:
        """
        Returns a dict of search parameters that should be included in an API
        request for this search.
        """
        return {
            "search_query": self.query,
            "id_list": ",".join(self.id_list),
            "sortBy": self.sort_by.value,
            "sortOrder": self.sort_order.value,
        }

    def results(self, offset: int = 0) -> Generator[arxiv.Result, None, None]:
        """
        Executes the specified search using a default arXiv API client. For info
        on default behavior, see `Client.__init__` and `Client.results`.

        **Deprecated** after 2.0.0; use `Client.results`.
        """
        return ArxivClient().results(self, offset=offset)


class ArxivClient(arxiv.Client):
    def _format_url(self, search: arxiv.Search, start: int, page_size: int) -> str:
        """
        Construct a request API for search that returns up to `page_size`
        results starting with the result at index `start`.
        """
        url_args = search._url_args()
        url_args: dict
        url_args.update(
            {
                "start": start,
                "max_results": page_size,
            }
        )
        url = self.query_url_format.format(urlencode(url_args))
        url = url.replace("%26", "&")
        return url


class ArxivSearchAPI(BaseSearchEngine):
    """
    ArXiv search API implementation inheriting from BaseSearchEngine.
    
    Provides search functionality for ArXiv preprint server with unified interface.
    
    Query prefixes supported:
    - ti: Title
    - au: Author
    - abs: Abstract
    - co: Comment
    - jr: Journal Reference
    - cat: Subject Category
    - rn: Report Number
    - id: Id (use id_list instead)
    - all: All of the above
    """

    def __init__(self):
        super().__init__()
        self.client = ArxivClient()
        self.max_results_limit = 2000  # ArXiv API limit

    def _query(self, query: str = '', id_list=None, start: int = 0, max_results: int = 10,
               sort_by: str = 'relevance', sort_order: str = 'descending', ):
        """
        Query the arXiv API and return the results as a feedparser feed.
        :param query: Full-text query. Optional, but if this is present, id_list is ignored.
        :param id_list: List of arXiv IDs. Optional, but if this is present, search_query is ignored.
        :param start: The index of the first result to return. Default is 0.
        :param max_results: The maximum number of results to return. Default is 10. Maximum is 2000.
        :param sort_by: The field by which to sort results. Default is 'relevance'. Other valid values are 'lastUpdatedDate', 'submittedDate'.
        :param sort_order: The sort order. Default is 'descending'. Other valid values are 'ascending'.
        """
        if id_list is None:
            id_list = []
        if not query:
            query = ''
        if max_results == 0:
            return []
        start = max(start, 0)
        max_results = min(max_results, 2000)
        search = arxiv.Search(query=query, id_list=id_list, max_results=max_results,
                              sort_by=arxiv.SortCriterion(sort_by), sort_order=arxiv.SortOrder(sort_order))
        results = self.client.results(search, offset=start)

        return results

    def _parse(self, results: list[arxiv.Result]) -> list[dict]:
        """
        Parse the results from the arXiv API and return a list of dictionaries.
        :param results: A feedparser feed containing the results of a query.
        """
        parsed_results = []
        for result in results:
            parsed_result = {
                'title': result.title,
                'abstract': result.summary,
                'authors': [author.name for author in result.authors],
                'doi': result.doi or '',
                'arxiv_id': result.get_short_id(),
                'year': result.published.year,
                'published_date': result.published.date().isoformat(),
                'updated_date': result.updated.date().isoformat(),
                'journal': result.journal_ref,
                'url': result.entry_id,
                'arxiv': result_to_dict(result)
            }
            parsed_results.append(parsed_result)
        return parsed_results

    def get_source_name(self) -> str:
        """Get the name of the data source."""
        return 'arxiv'
    
    def _search(self, query: str, **kwargs) -> Tuple[List[Dict], Dict]:
        """
        Execute raw search against ArXiv API.
        
        Args:
            query: Search query string
            **kwargs: Additional search parameters including:
                - num_results: Number of results to return
                - id_list: List of ArXiv IDs to search
                - sort_by: Sort criterion ('relevance', 'lastUpdatedDate', 'submittedDate')
                - sort_order: Sort order ('ascending', 'descending')
                - year: Year filter
                
        Returns:
            Tuple[List[Dict], Dict]: Raw results and metadata
        """
        try:
            # Extract parameters
            num_results = kwargs.get('num_results', self.default_results)
            id_list = kwargs.get('id_list', [])
            sort_by = kwargs.get('sort_by', 'relevance')
            sort_order = kwargs.get('sort_order', 'descending')
            year = kwargs.get('year')
            
            if num_results == 0:
                return [], {'query': query}

            # Build complete search query including year conditions
            search_query = query if query else ''
            if year:
                start, end = year_split(year)
                if start == end:
                    year_filter = "{}010101600 TO {}01010600".format(start, int(end) + 1)
                else:
                    year_filter = "{}010101600 TO {}01010600".format(start, int(end) + 1)
                # Add year condition to search query
                search_query = f"{search_query}&submittedDate:[{year_filter}]" if search_query else f"submittedDate:[{year_filter}]"

            # Execute query
            results = self._query(search_query, id_list, max_results=num_results, 
                                sort_by=sort_by, sort_order=sort_order)
            
            # Parse results
            parsed_results = self._parse(results)

            metadata = {
                'query': search_query,
                'original_query': query,
                'year_filter': year,
                'sort_by': sort_by,
                'sort_order': sort_order,
                'requested_results': num_results
            }
            
            return parsed_results, metadata
            
        except Exception as e:
            self.logger.error(f"Error during ArXiv search: {e}")
            raise NetworkError(f"ArXiv search failed: {e}") from e
    
    def _response_format(self, results: List[Dict], source: str) -> List[Dict]:
        """
        Format raw ArXiv results into standardized LiteratureSchema format.
        
        Args:
            results: Raw search results from ArXiv API
            source: Data source name ('arxiv')
            
        Returns:
            List[Dict]: Formatted results conforming to LiteratureSchema
        """
        formatted_results = []
        
        for item in results:
            try:
                # Create article schema
                article = ArticleSchema(
                    primary_doi=item.get('doi'),
                    title=item.get('title', ''),
                    abstract=item.get('abstract'),
                    publication_year=item.get('year'),
                    publication_date=item.get('published_date'),
                    updated_date=item.get('updated_date'),
                    is_open_access=True,  # ArXiv is open access
                    open_access_url=item.get('pdf_url')
                )
                
                # Create authors
                authors = []
                for i, author_name in enumerate(item.get('authors', [])):
                    if author_name and author_name.strip():
                        authors.append(AuthorSchema(
                            full_name=author_name.strip(),
                            author_order=i + 1
                        ))
                
                # Create venue schema
                venue = VenueSchema(
                    venue_name=item.get('journal') or 'arXiv',
                    venue_type=VenueType.PREPRINT_SERVER
                )
                
                # Create identifiers
                identifiers = []
                
                # Add DOI if available
                doi = item.get('doi')
                if doi and str(doi).strip():
                    identifiers.append(IdentifierSchema(
                        identifier_type=IdentifierType.DOI,
                        identifier_value=str(doi).strip(),
                        is_primary=True
                    ))
                
                # Add ArXiv ID
                arxiv_id = item.get('arxiv_id')
                if arxiv_id and str(arxiv_id).strip():
                    identifiers.append(IdentifierSchema(
                        identifier_type=IdentifierType.ARXIV_ID,
                        identifier_value=str(arxiv_id).strip(),
                        is_primary=not bool(item.get('doi'))  # Primary if no DOI
                    ))
                
                # Create categories from ArXiv categories
                categories = []
                for category in item.get('categories', []):
                    if category and category.strip():
                        categories.append(CategorySchema(
                            category_name=category.strip(),
                            category_type=CategoryType.ARXIV_CATEGORY
                        ))
                
                # Create literature schema
                literature = LiteratureSchema(
                    article=article,
                    authors=authors,
                    venue=venue,
                    identifiers=identifiers,
                    categories=categories,
                    source_specific={
                        'source': source,
                        'raw_data': item,
                        'arxiv_url': item.get('url'),
                        'pdf_url': item.get('pdf_url'),
                        'categories': item.get('categories', [])
                    }
                )
                
                # Validate the schema
                is_valid, errors = literature.validate()
                if not is_valid:
                    self.logger.warning(f"Schema validation failed for ArXiv item: {errors}")
                    # Skip invalid items if they have critical errors (like missing title)
                    if any("title is required" in error for error in errors):
                        continue
                
                formatted_results.append(literature.to_dict())
                
            except Exception as e:
                self.logger.error(f"Error formatting ArXiv result: {e}")
                # Skip malformed results and continue processing other results
                continue
        
        return formatted_results
    
    def validate_params(self, query: str, **kwargs) -> bool:
        """
        Validate ArXiv-specific search parameters.
        
        Args:
            query: Search query string
            **kwargs: Additional parameters
            
        Returns:
            bool: True if parameters are valid
        """
        # Call parent validation first
        if not super().validate_params(query, **kwargs):
            return False
        
        # ArXiv-specific validation
        num_results = kwargs.get('num_results', self.default_results)
        if num_results > self.max_results_limit:
            self.logger.error(f"num_results exceeds ArXiv limit of {self.max_results_limit}")
            return False
        
        # Validate sort parameters
        sort_by = kwargs.get('sort_by', 'relevance')
        valid_sort_by = ['relevance', 'lastUpdatedDate', 'submittedDate']
        if sort_by not in valid_sort_by:
            self.logger.error(f"Invalid sort_by: {sort_by}. Must be one of {valid_sort_by}")
            return False
        
        sort_order = kwargs.get('sort_order', 'descending')
        valid_sort_order = ['ascending', 'descending']
        if sort_order not in valid_sort_order:
            self.logger.error(f"Invalid sort_order: {sort_order}. Must be one of {valid_sort_order}")
            return False
        
        # Validate id_list if provided
        id_list = kwargs.get('id_list', [])
        if id_list and not isinstance(id_list, list):
            self.logger.error("id_list must be a list")
            return False
        
        return True
    
    # Backward compatibility method
    def search_legacy(self, query: str = None, id_list: list[str] = None, num_results: int = 10,
                     sort_by: str = 'relevance', sort_order: str = 'descending', year: str = None):
        """
        Legacy search method for backward compatibility.
        
        This method maintains the original interface while using the new base class architecture.
        """
        # Convert parameters to new format
        kwargs = {
            'num_results': num_results,
            'id_list': id_list or [],
            'sort_by': sort_by,
            'sort_order': sort_order,
            'year': year
        }
        
        # Use the new search method
        formatted_results, metadata = self.search(query or '', **kwargs)
        
        # Convert back to legacy format if needed
        legacy_results = []
        for result in formatted_results:
            legacy_results.append(result['source_specific']['raw_data'])
        
        return legacy_results, metadata
