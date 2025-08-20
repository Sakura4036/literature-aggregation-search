import time
import traceback
from enum import Enum

import requests
import logging
from datetime import datetime, timedelta
import threading
from .utils import year_split
from .response_formatter import ResponseFormatter

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


class WosSearchAPI:
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
        self.api_keys = api_keys or []
        self.api_keys = list(set(self.api_keys))
        if not self.api_keys:
            # Instead of raising an error, we can allow it to be initialized
            # and the search method will handle the case of no keys.
            pass
        self.key_manager = WosApiKeyManager(self.api_keys)
        self.limit = 50

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

    def search(self, query: str,
               query_type: str = 'TS',
               year: str = "",
               document_type: str = '',
               limit: int = 50,
               sort_field: str = 'RS+D',
               db: str = 'WOK') -> tuple[list[dict], dict]:
        """
        Search Web of Science Core Collection.
        :param query: query string
        :param query_type: query type, default is 'TS'(Topic, Title, Abstract, Author Keywords, Keywords Plus)
        :param year: publication year, format: 'YYYY' or 'YYYY-YYYY'
        :param document_type: document type, default is ''
        :param limit: number of results to return
        :param sort_field: sort field, default is 'RS+D'(Relevance + Descending)
        :param db: database name, default is 'WOK'(all databases), 'WOS' for Web of Science Core Collection,
        :return: list of papers, metadata
        """
        if not limit:
            return [], {}
        result, metadata = self.query(query, query_type, year, document_type, limit, sort_field, db)
        logger.debug(f"wos_search result num: {len(result)}", )

        # Format the results
        formatted_results = [ResponseFormatter.format(r, 'wos') for r in result]

        return formatted_results, metadata
