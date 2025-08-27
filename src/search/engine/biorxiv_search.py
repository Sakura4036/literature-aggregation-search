import logging
from datetime import datetime
from typing import Optional, Tuple, List, Dict

import requests

from src.models.enums import IdentifierType, VenueType, CategoryType, PublicationTypeSource
from src.models.schemas import (
    LiteratureSchema, ArticleSchema, AuthorSchema, VenueSchema,
    IdentifierSchema, CategorySchema, PublicationTypeSchema
)
from src.search.engine.base_engine import BaseSearchEngine, NetworkError
from src.search.utils import year_split

logger = logging.getLogger(__name__)


class BioRxivSearchAPI(BaseSearchEngine):
    """
    bioRxiv Search API implementation inheriting from BaseSearchEngine.
    
    Provides search functionality for bioRxiv preprint server with unified interface.
    API文档: https://api.biorxiv.org/
    """
    base_url: str = "https://api.biorxiv.org"

    def __init__(self):
        """Initialize bioRxiv search API"""
        super().__init__()
        self.limit = 100  # bioRxiv API每页最大返回100条结果
        self.max_results_limit = 10000  # Set reasonable limit for bioRxiv

    def get_source_name(self) -> str:
        """Get the name of the data source."""
        return 'biorxiv'

    def _process_response(self, response: dict) -> list[dict]:
        """
        处理bioRxiv API的响应数据，转换为统一格式
        
        Args:
            response: bioRxiv API的原始响应数据
            
        Returns:
            list[dict]: 处理后的论文数据列表
        """
        results = []
        if not response or 'collection' not in response:
            return results

        for paper in response['collection']:
            # 处理作者信息
            authors = []
            if paper.get('authors'):
                authors = [author.strip() for author in paper['authors'].split(';')]

            # 处理日期
            try:
                published_date = datetime.strptime(paper.get('date', ''), '%Y-%m-%d').date()
                year = published_date.year
                published_date = published_date.isoformat()
            except:
                published_date = None
                year = None

            # 构建统一格式的论文数据
            format_paper = {
                'title': paper.get('title', ''),
                'abstract': paper.get('abstract', ''),
                'authors': authors,
                'doi': paper.get('doi', ''),
                'year': year,
                'published_date': published_date,
                'journal': paper.get('server', 'biorxiv'),  # 预印本服务器名称
                'types': ['Preprint'],  # bioRxiv都是预印本
                'biorxiv': paper  # 保存原始数据
            }
            results.append(format_paper)

        return results

    def _query_once(self,
                    query: str,
                    server: str = 'biorxiv',
                    cursor: int = 0,
                    interval: Optional[str] = None) -> Tuple[int, list[dict], str]:
        """
        执行一次bioRxiv API查询
        
        Args:
            query: 查询DOI
            server: 服务器类型(biorxiv或medrxiv)
            cursor: 分页起始位置
            interval: 日期范围，格式为'YYYY-MM-DD/YYYY-MM-DD'
            
        Returns:
            Tuple[int, list[dict], str]: (总结果数, 论文列表, 请求URL)
        """
        # 构建API URL
        if query.startswith('10.1101/'):  # 如果是DOI查询
            url = f"{self.base_url}/details/{server}/{query}/na/json"
        else:  # 如果是日期范围查询
            url = f"{self.base_url}/details/{server}/{interval}/{cursor}/json"

        logger.debug(f"BioRxiv API request: {url}")

        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                messages = data.get('messages', [{}])[0]
                if messages.get('status') == 'error':
                    logger.error(f"BioRxiv API request error: {messages.get('message')}")
                    return 0, [], url
                total = int(messages.get('total', 0))
                if not total:
                    total = len(data.get('collection', []))
                results = self._process_response(data)
                return total, results, url
            else:
                logger.error(f"BioRxiv API request failed: {response.status_code}")
                return 0, [], url
        except Exception as e:
            logger.error(f"BioRxiv API request error: {e}")
            return 0, [], url

    def query(self,
              query: str = '',
              server: str = 'biorxiv',
              year: str = '',
              num_results: int = 50) -> Tuple[list[dict], dict]:
        """
        查询bioRxiv论文
        
        Args:
            query: 查询DOI
            server: 服务器类型(biorxiv或medrxiv)
            year: 年份范围，格式为'YYYY-' 或 '-YYYY' 或 'YYYY-YYYY'
            num_results: 需要返回的结果数量
            
        Returns:
            Tuple[list[dict], dict]: (论文列表, 元数据)
        """
        if not num_results:
            return [], {}

        # 处理年份范围
        if year:
            start, end = year_split(year)
            if start == end:
                interval = f"{year}-01-01/{year}-12-31"
            else:
                interval = f"{start}-01-01/{end}-01-01"
        else:
            interval = None

        # 执行查询
        total, results, url = self._query_once(query, server, interval=interval)

        metadata = {
            "total": total,
            "query": query,
            "url": url,
            'server': server,
        }

        if total == 0:
            return [], metadata

        # 如果需要更多结果，继续查询
        if len(results) < num_results and len(results) < total:
            cursor = self.limit
            while cursor < total and len(results) < num_results:
                _, more_results, _ = self._query_once(query, server, cursor=cursor, interval=interval)
                results.extend(more_results)
                cursor += self.limit

        # 截取所需数量的结果
        results = results[:num_results]

        return results, metadata

    def _search(self, query: str, **kwargs) -> Tuple[List[Dict], Dict]:
        """
        Execute raw search against bioRxiv API.
        
        Args:
            query: Search query string (DOI or empty for date range search)
            **kwargs: Additional search parameters including:
                - num_results: Number of results to return
                - year: Year range filter
                - server: Server type ('biorxiv' or 'medrxiv')
                
        Returns:
            Tuple[List[Dict], Dict]: Raw results and metadata
        """
        try:
            # Extract parameters
            num_results = kwargs.get('num_results', self.default_results)
            year = kwargs.get('year', '')
            server = kwargs.get('server', 'biorxiv')
            
            # Use the existing query method
            results, metadata = self.query(
                query=query,
                year=year,
                num_results=num_results,
                server=server
            )
            
            self.logger.debug(f"bioRxiv search returned {len(results)} results")
            return results, metadata
            
        except Exception as e:
            self.logger.error(f"Error during bioRxiv search: {e}")
            raise NetworkError(f"bioRxiv search failed: {e}") from e

    def _response_format(self, results: List[Dict]) -> List[Dict]:
        """
        Format raw bioRxiv results into standardized LiteratureSchema format.
        
        Args:
            results: Raw search results from bioRxiv API
            
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
                    is_open_access=True,  # bioRxiv is open access
                    language="eng"  # bioRxiv is primarily English
                )
                
                # Create authors
                authors = []
                for i, author_name in enumerate(item.get('authors', [])):
                    if author_name and author_name.strip():
                        authors.append(AuthorSchema(
                            full_name=author_name.strip(),
                            author_order=i + 1
                        ))
                
                # Create venue schema - bioRxiv is a preprint server
                venue = VenueSchema(
                    venue_name=item.get('journal', 'bioRxiv'),
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
                
                # Create categories from bioRxiv category
                categories = []
                # bioRxiv has category information in the raw data
                raw_data = item.get('biorxiv', {})
                category = raw_data.get('category')
                if category and category.strip():
                    categories.append(CategorySchema(
                        category_name=category.strip(),
                        category_type=CategoryType.OTHER  # bioRxiv uses its own categorization
                    ))
                
                # Create publication types
                publication_types = []
                for pub_type in item.get('types', []):
                    if pub_type and pub_type.strip():
                        publication_types.append(PublicationTypeSchema(
                            type_name=pub_type.strip(),
                            source_type=PublicationTypeSource.GENERAL
                        ))
                
                # Create literature schema
                literature = LiteratureSchema(
                    article=article,
                    authors=authors,
                    venue=venue,
                    identifiers=identifiers,
                    categories=categories,
                    publication_types=publication_types,
                    source_specific={
                        'source': self.get_source_name(),
                        'raw_data': item,
                        'server': raw_data.get('server', 'bioRxiv'),
                        'version': raw_data.get('version'),
                        'license': raw_data.get('license'),
                        'jatsxml': raw_data.get('jatsxml'),
                        'author_corresponding': raw_data.get('author_corresponding'),
                        'author_corresponding_institution': raw_data.get('author_corresponding_institution')
                    }
                )
                
                # Validate the schema
                is_valid, errors = literature.validate()
                if not is_valid:
                    self.logger.warning(f"Schema validation failed for bioRxiv item: {errors}")
                    # Skip invalid items if they have critical errors (like missing title)
                    if any("title is required" in error for error in errors):
                        continue
                
                formatted_results.append(literature.to_dict())
                
            except Exception as e:
                self.logger.error(f"Error formatting bioRxiv result: {e}")
                # Skip malformed results and continue processing other results
                continue
        
        return formatted_results


if __name__ == "__main__":
    api = BioRxivSearchAPI()
    print(api.search('10.1101/2025.08.04.668552', num_results=1))