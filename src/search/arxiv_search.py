import logging
import math
from typing import Generator, List, Dict
import arxiv
from urllib.parse import urlencode
from .utils import year_split
from .response_formatter import ResponseFormatter

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


class ArxivSearchAPI:
    # base_url = "http://export.arxiv.org/api/{method_name}?{parameters}"
    # query_url = 'http://export.arxiv.org/api/query?'
    """
    query prefix
    ti: Title
    au: Author
    abs: Abstract
    co: Comment
    jr: Journal Reference
    cat: Subject Category
    rn: Report Number
    id: Id (use id_list instead)
    all: All of the above
    """

    def __init__(self):
        self.client = ArxivClient()

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

    def search(self, query: str = None, id_list: list[str] = None, num_results: int = 10,
               sort_by: str = 'relevance', sort_order: str = 'descending', year: str = None):
        """
        Query the arXiv API and return the results as a list of dictionaries.
        :param query: Full-text query. Optional, but if this is present, id_list is ignored.
        :param id_list: List of arXiv IDs. Optional, but if this is present, search_query is ignored.
        :param num_results: The maximum number of results to return. Default is 10. Maximum is 2000.
        :param sort_by: The field by which to sort results. Default is 'relevance'. Other valid values are 'lastUpdatedDate', 'submittedDate'.
        :param sort_order: The sort order. Default is 'descending'. Other valid values are 'ascending'.
        :param year: The year of publication. Optional. If present, the search will be restricted to this year.
        :return: A list of dictionaries containing the results of the query, and a dictionary containing metadata.
        """
        if num_results == 0:
            return [], {}

        # 构建完整的search_query，包含年份条件
        search_query = query if query else ''
        if year:
            start, end = year_split(year)
            if start == end:
                year = "{}010101600 TO {}01010600".format(start, int(end) + 1)
            else:
                year = "{}010101600 TO {}01010600".format(start, end)
            # 将年份条件作为search_query的一部分
            search_query = f"{search_query}&submittedDate:[{year}]" if search_query else f"submittedDate:[{year}]"

        results = self._query(search_query, id_list, max_results=num_results, sort_by=sort_by,
                              sort_order=sort_order)
        parsed_results = self._parse(results)

        # Format the results
        formatted_results = [ResponseFormatter.format(result, 'arxiv') for result in parsed_results]

        metadata = {
            'query': search_query,
        }
        return formatted_results, metadata
