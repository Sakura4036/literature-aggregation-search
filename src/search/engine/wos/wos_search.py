import time
import traceback
from enum import Enum
from typing import Dict, List, Tuple, Any, Optional

import requests
import logging
from datetime import datetime, timedelta
import threading

from src.search.engine.base_engine import BaseSearchEngine, NetworkError, FormatError
from src.search.utils import year_split
from src.models.schemas import (
    LiteratureSchema, ArticleSchema, AuthorSchema, VenueSchema, 
    PublicationSchema, IdentifierSchema, CategorySchema, PublicationTypeSchema
)
from src.models.enums import IdentifierType, VenueType, CategoryType, PublicationTypeSource

logger = logging.getLogger(__name__)


class WOS_QUERY_TYPES(str, Enum):
    ALL = 'ALL'
    TITLE = 'TI'
    AUTHOR = 'AU'
    DOI = 'DO'
    ISSN = 'IS'
    PMID = 'PMID'
    KEYWORDS = 'TS'


class WOS_DOCUMENT_TYPES(str, Enum):
    ARTICLE = 'Article'
    REVIEW = 'Review'
    BOOK = 'Book'
    MEETING = 'Meeting'


def check_document_type(document_type: str):
    """
    Check the publication type.
    WOS support: https://webofscience.help.clarivate.com/en-us/Content/document-types.html
    """
    if not document_type or document_type.lower() == 'all':
        return ''
    if document_type in ['Article', 'Review']:
        return document_type
    else:
        raise ValueError(f"Invalid publication type: {document_type}")


class WosApiKeyManager:
    """管理多个WOS API key的使用"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, api_keys: list[str] = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, api_keys: list[str] = None):
        if self._initialized:
            return

        self.api_keys = api_keys
        self.usage_count = {key: 0 for key in api_keys}  # 记录每个key的使用次数
        self.daily_limit = 50  # WOS API每个key每天的调用限制
        self.current_key_index = 0
        self._last_reset = datetime.now()

        # 启动自动重置线程
        self._start_auto_reset()
        self._initialized = True

    def _start_auto_reset(self):
        """启动自动重置线程"""

        def reset_checker():
            while True:
                now = datetime.now()
                # 如果已经过了一天
                if (now - self._last_reset).days >= 1:
                    self.reset_usage()
                    self._last_reset = now
                # 计算到下一个0点的秒数
                next_day = (now + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                sleep_seconds = (next_day - now).total_seconds()
                time.sleep(sleep_seconds)

        # 启动后台线程
        thread = threading.Thread(target=reset_checker, daemon=True)
        thread.start()

    def get_next_available_key(self) -> str:
        """获取下一个可用的API key"""
        if not self.api_keys:
            raise ValueError("No WOS API keys available")

        with self._lock:
            # 检查所有key的使用情况
            start_index = self.current_key_index
            while True:
                current_key = self.api_keys[self.current_key_index]
                if self.usage_count[current_key] < self.daily_limit:
                    return current_key

                # 移动到下一个key
                self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)

                # 如果已经检查了所有的key
                if self.current_key_index == start_index:
                    raise ValueError("All WOS API keys have reached daily limit")

    def increment_usage(self, api_key: str):
        """增加指定key的使用计数"""
        with self._lock:
            if api_key in self.usage_count:
                self.usage_count[api_key] += 1

    def reset_usage(self):
        """重置所有key的使用计数"""
        with self._lock:
            self.usage_count = {key: 0 for key in self.api_keys}
            logger.info(f"Reset WOS API keys usage count at {datetime.now()}")

    def get_usage_info(self) -> dict:
        """获取所有key的使用情况"""
        with self._lock:
            return {
                'usage_count': self.usage_count.copy(),
                'last_reset': self._last_reset,
                'next_reset': (self._last_reset + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            }


class WosSearchAPI(BaseSearchEngine):
    """
    Web of Science Search API tool provider.
    API documentation: https://api.clarivate.com/swagger-ui/?apikey=none&url=https%3A%2F%2Fdeveloper.clarivate.com%2Fapis%2Fwos-starter%2Fswagger
    """
    base_url: str = 'https://api.clarivate.com/apis/wos-starter/v1/documents'
    switch_grammar = {
        # "+": 'AND',
        # "|": 'OR',
        # "-": 'NOT',
    }

    def __init__(self, api_keys: list[str] = None) -> None:
        """Initialize Web of Science Search API tool provider."""
        super().__init__()
        self.api_keys = api_keys or []
        self.api_keys = list(set(self.api_keys))
        if not self.api_keys:
            # Instead of raising an error, we can allow it to be initialized
            # and the search method will handle the case of no keys.
            pass
        self.key_manager = WosApiKeyManager(self.api_keys)
        self.limit = 50

    def get_source_name(self) -> str:
        """Get the name of the data source."""
        return "wos"

    def check_query(self, query: str):
        for key, value in self.switch_grammar.items():
            query = query.replace(key, value)
        return f"({query})"

    def get_query(self, query: str, query_type: str = 'TS') -> str:
        """
        Get parameters for Web of Science Search API.
        :param query: query string
        :param query_type: query type: TI(title), AU(author), TS(title, abstract, author keywords, keywords plus), DO(doi), IS(ISSN),  PMID(PubMed ID),
        """
        assert query_type in [qt.value for qt in WOS_QUERY_TYPES], 'Invalid query type'
        query = "{}={}".format(query_type, self.check_query(query))
        return query

    @staticmethod
    def _process_response(response: dict) -> list[dict]:
        """
        Process response from Web of Science Search API.
        response example:

        """
        result = []
        if response and 'hits' in response:
            for wos_document in response['hits']:
                identifiers = wos_document.get('identifiers')
                if not identifiers:
                    continue
                if wos_document.get('names'):
                    authors = wos_document['names'].get('authors') or []
                    authors = [au.get('displayName') for au in authors if au.get('displayName')]
                    assert isinstance(authors, list), f"Invalid authors: {authors}"
                else:
                    authors = []
                if wos_document.get('types'):
                    types = wos_document['types']
                    if isinstance(types, str):
                        types = types.split(',')
                    elif isinstance(types, list):
                        types = types
                    else:
                        logger.debug(f"Invalid types: {types}")
                        types = []
                else:
                    types = []

                year = wos_document['source'].get('publishYear')  # 2021
                month = wos_document['source'].get('publishMonth')  # NOV
                # 将月份英文简写转换为数字
                month_map = {
                    'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04',
                    'MAY': '05', 'JUN': '06', 'JUL': '07', 'AUG': '08',
                    'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
                }
                if month and '-' in month:
                    start_month, end_month = month.split('-')
                    month = start_month
                else:
                    month = month_map.get(month, month) if month else month
                try:
                    if year and month:
                        published_date = f"{year}-{month}"
                        published_date = datetime.strptime(published_date, '%Y-%m').date().isoformat()
                    else:
                        published_date = None
                except:
                    published_date = None

                format_paper = {
                    # 'wos_uid': wos_document.get('uid'),
                    'title': wos_document.get('title', ''),
                    'abstract': wos_document.get('abstract', ''),
                    'doi': identifiers.get('doi', ''),
                    'pmid': identifiers.get('pmid', ''),
                    'issn': identifiers.get('issn', ''),
                    'eissn': identifiers.get('eissn', ''),
                    'year': year,
                    'published_date': published_date,
                    # https://webofscience.help.clarivate.com/en-us/Content/document-types.html
                    'types': types,
                    'authors': authors,
                    'journal': wos_document['source'].get('sourceTitle'),
                    'volume': wos_document['source'].get('volume'),
                    'issue': wos_document['source'].get('issue'),
                    'wos': wos_document
                }
                result.append(format_paper)
        return result

    def query_once(self, query: str, limit: int = 50, page: int = 1, sort_field: str = 'RS+D', db: str = 'WOK') -> tuple[int, list[dict], str]:
        """
        Query Web of Science Search API once.

        Args:
            query: query string
            limit: number of results to return
            page: page number, default is 1(start from 1)
            sort_field: sort field, default is 'RS+D'(Relevance + Descending)
            db: database name, default is 'WOK'(all databases), 'WOS' for Web of Science Core Collection,
             Available values : BCI, BIOABS, BIOSIS, CCC, DIIDW, DRCI, MEDLINE, PPRN, WOK, WOS, ZOOREC
        """
        if limit <= 0:
            return 0, [], ""

        request_str = f'{self.base_url}?q={query}&limit={limit}&page={page}&sortField={sort_field}&db={db}'
        logger.debug(f"Web of Science API request: {request_str}")

        while True:  # 添加循环以处理API key切换
            try:
                # 获取可用的API key
                try:
                    api_key = self.key_manager.get_next_available_key()
                except ValueError as e:
                    logger.error(f"WOS API key error: {e}")
                    return 0, [], ""

                response = requests.get(request_str, headers={'X-ApiKey': api_key})

                if response.status_code == 200:
                    self.key_manager.increment_usage(api_key)
                    response = response.json()
                    logger.debug("metadata:", response['metadata'])
                    total = response['metadata']['total']
                    data = self._process_response(response)
                    return total, data, request_str
                elif response.status_code == 429:  # Too Many Requests
                    # 将当前key的使用次数设置为达到上限
                    logger.warning(f"API key {api_key} reached rate limit (429 response)")
                    with self.key_manager._lock:
                        self.key_manager.usage_count[api_key] = self.key_manager.daily_limit
                    continue  # 继续循环尝试下一个key
                else:
                    logger.debug(f"Web of Science API request failed: {response.json()}")
                    return 0, [], request_str

            except Exception as e:
                logger.error(f"Web of Science API request failed: {e}")
                traceback.print_exc()
                return 0, [], request_str

    def query(self, query: str, query_type: str = 'TS', year: str = "", document_type: str = '',
              num_results: int = 50, sort_field: str = 'RS+D', db: str = 'WOK') -> tuple[list[dict], dict]:
        """
        web of science api: https://api.clarivate.com/swagger-ui/?apikey=none&url=https%3A%2F%2Fdeveloper.clarivate.com%2Fapis%2Fwos-starter%2Fswagger
        query_type:
            TI - Title
            AU - Author
            DO - DOI
            IS - ISSN
            DT - Document Type
            TS - Topic, Title, Abstract, Author Keywords, Keywords Plus
            etc.
        sortField: Order by field(s). Field name and order by clause separated by '+', use A for ASC and D for DESC, ex: PY+D. Multiple values are separated by comma. Supported fields:
                    LD - Load Date
                    PY - Publication Year
                    RS - Relevance
                    TC - Times Cited
        """
        query = self.get_query(query, query_type)

        if year:
            start, end = year_split(year)
            year = f"{start}-{end}" if end else start
            query = f"{query} AND PY=({year})"

        document_type = check_document_type(document_type)
        if document_type:
            query = f"{query} AND DT=({document_type})"

        limit = min(num_results, self.limit)
        page = 1
        total, data, query_url = self.query_once(query, limit, page=page, sort_field=sort_field, db=db)
        metadata = {
            "total": total,
            "query": query,
            "query_type": query_type,
            'url': query_url,
        }
        if total == 0:
            return [], metadata

        result = data
        rest_num = min(num_results, total) - limit

        while rest_num > 0:
            limit = min(rest_num, self.limit)
            page += 1
            total, data, query_url = self.query_once(query, limit, page, sort_field, db)
            if total == 0:
                break

            result.extend(data)
            rest_num -= limit
            time.sleep(10)

        return result, metadata

    def _search(self, query: str, **kwargs) -> Tuple[List[Dict], Dict]:
        """
        Execute raw search against Web of Science API.
        
        Args:
            query: Search query string
            **kwargs: Additional search parameters including:
                - query_type: Query type (default: 'TS')
                - year: Publication year filter
                - document_type: Document type filter
                - num_results: Number of results to return (default: 50)
                - sort_field: Sort field (default: 'RS+D')
                - db: Database name (default: 'WOK')
                
        Returns:
            Tuple[List[Dict], Dict]: Raw results and metadata
        """
        # Extract parameters with defaults
        query_type = kwargs.get('query_type', 'TS')
        year = kwargs.get('year', '')
        document_type = kwargs.get('document_type', '')
        num_results = kwargs.get('num_results', 50)
        sort_field = kwargs.get('sort_field', 'RS+D')
        db = kwargs.get('db', 'WOK')
        
        if not num_results:
            return [], {}
            
        try:
            result, metadata = self.query(query, query_type, year, document_type, num_results, sort_field, db)
            logger.debug(f"wos_search result num: {len(result)}")
            return result, metadata
        except Exception as e:
            logger.error(f"WoS search failed: {e}")
            raise NetworkError(f"WoS API request failed: {e}")

    def _response_format(self, results: List[Dict]) -> List[Dict]:
        """
        Format raw WoS search results into standardized LiteratureSchema format.
        
        Args:
            results: Raw search results from WoS API
            
        Returns:
            List[Dict]: List of formatted results conforming to LiteratureSchema
        """
        formatted_results = []
        
        for item in results:
            try:
                # Extract WoS-specific data
                wos_data = item.get('wos', {})
                
                # Create article schema
                article = ArticleSchema(
                    primary_doi=item.get('doi', '').strip() or None,
                    title=item.get('title', '').strip(),
                    abstract=item.get('abstract', '').strip() or None,
                    publication_year=item.get('year'),
                    publication_date=item.get('published_date'),
                    citation_count=self._extract_citation_count(wos_data),
                    is_open_access=False  # WoS doesn't provide this info directly
                )
                
                # Create authors
                authors = []
                raw_authors = item.get('authors', [])
                for i, author_name in enumerate(raw_authors):
                    if author_name and author_name.strip():
                        authors.append(AuthorSchema(
                            full_name=author_name.strip(),
                            author_order=i + 1
                        ))
                
                # Create venue schema
                venue = VenueSchema(
                    venue_name=item.get('journal', '').strip(),
                    venue_type=VenueType.JOURNAL,  # WoS primarily contains journal articles
                    issn_print=item.get('issn', '').strip() or None,
                    issn_electronic=item.get('eissn', '').strip() or None
                )
                
                # Create publication schema
                publication = PublicationSchema(
                    volume=item.get('volume', '').strip() or None,
                    issue=item.get('issue', '').strip() or None,
                    page_range=self._extract_page_range(wos_data)
                )
                
                # Create identifiers
                identifiers = []
                if item.get('doi'):
                    identifiers.append(IdentifierSchema(
                        identifier_type=IdentifierType.DOI,
                        identifier_value=item['doi'].strip(),
                        is_primary=True
                    ))
                
                if item.get('pmid'):
                    identifiers.append(IdentifierSchema(
                        identifier_type=IdentifierType.PMID,
                        identifier_value=str(item['pmid']).strip()
                    ))
                
                if wos_data.get('uid'):
                    identifiers.append(IdentifierSchema(
                        identifier_type=IdentifierType.WOS_UID,
                        identifier_value=wos_data['uid'].strip()
                    ))
                
                # Create categories from WoS types
                categories = []
                wos_types = item.get('types', [])
                if wos_types:
                    for wos_type in wos_types:
                        if wos_type and wos_type.strip():
                            categories.append(CategorySchema(
                                category_name=wos_type.strip(),
                                category_type=CategoryType.WOS_CATEGORY
                            ))
                
                # Create publication types
                publication_types = []
                if wos_types:
                    for wos_type in wos_types:
                        if wos_type and wos_type.strip():
                            publication_types.append(PublicationTypeSchema(
                                type_name=wos_type.strip(),
                                source_type=PublicationTypeSource.WOS
                            ))
                
                # Create the complete literature schema
                literature = LiteratureSchema(
                    article=article,
                    authors=authors,
                    venue=venue,
                    publication=publication,
                    identifiers=identifiers,
                    categories=categories,
                    publication_types=publication_types,
                    source_specific={
                        'source': self.get_source_name(),
                        'raw_data': item,
                        'wos_uid': wos_data.get('uid'),
                        'source_types': wos_data.get('sourceTypes', []),
                        'links': wos_data.get('links', {}),
                        'keywords': wos_data.get('keywords', {})
                    }
                )
                
                # Validate and add to results
                is_valid, errors = literature.validate()
                if not is_valid:
                    logger.warning(f"WoS result validation failed: {errors}")
                
                formatted_results.append(literature.to_dict())
                
            except Exception as e:
                logger.error(f"Error formatting WoS result: {e}")
                # Continue processing other results
                continue
        
        return formatted_results

    def _extract_citation_count(self, wos_data: Dict) -> int:
        """Extract citation count from WoS data."""
        try:
            citations = wos_data.get('citations', [])
            if citations and isinstance(citations, list):
                for citation in citations:
                    if citation.get('db') == 'WOS':
                        return citation.get('count', 0)
            return 0
        except Exception:
            return 0

    def _extract_page_range(self, wos_data: Dict) -> Optional[str]:
        """Extract page range from WoS data."""
        try:
            source = wos_data.get('source', {})
            pages = source.get('pages', {})
            if isinstance(pages, dict):
                return pages.get('range')
            return None
        except Exception:
            return None

    def search(self, query: str,
               query_type: str = 'TS',
               year: str = None,
               document_type: str = '',
               num_results: int = 50,
               sort_field: str = 'RS+D',
               db: str = 'WOK') -> tuple[list[dict], dict]:
        """
        Search Web of Science Core Collection.
        
        This method maintains backward compatibility while using the new base engine architecture.
        
        :param query: query string
        :param query_type: query type, default is 'TS'(Topic, Title, Abstract, Author Keywords, Keywords Plus)
        :param year: publication year, format: 'YYYY' or 'YYYY-YYYY'
        :param document_type: document type, default is ''
        :param num_results: number of results to return
        :param sort_field: sort field, default is 'RS+D'(Relevance + Descending)
        :param db: database name, default is 'WOK'(all databases), 'WOS' for Web of Science Core Collection,
        :return: list of papers, metadata
        """
        # Use the new base engine search method
        kwargs = {
            'query_type': query_type,
            'year': year,
            'document_type': document_type,
            'num_results': num_results,
            'sort_field': sort_field,
            'db': db
        }
        
        return super().search(query, **kwargs)
