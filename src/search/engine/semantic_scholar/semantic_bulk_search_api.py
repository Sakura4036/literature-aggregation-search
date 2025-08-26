import logging
import time
import traceback

from typing import Dict, List, Tuple, Optional
from .model import SemanticScholarPaper, SemanticResultFormatter
from src.search.engine.base_engine import BaseSearchEngine, NetworkError


logger = logging.getLogger(__name__)

normal_document_type_to_semantic = {
    'Review': 'Review',
    'Article': 'JournalArticle',
    'Book': 'Book',
}

semantic_document_type_to_normal = {v: k for k, v in normal_document_type_to_semantic.items()}


def document_type_to_semantic(document_type: str):
    if not document_type or document_type.lower() == 'all':
        return ''
    if document_type in normal_document_type_to_semantic:
        return normal_document_type_to_semantic[document_type]
    else:
        raise ValueError(f"Invalid publication type: {document_type}")

def document_type_to_normal(document_type: str):
    if document_type in semantic_document_type_to_normal:
        return semantic_document_type_to_normal[document_type]
    else:
        return document_type

class SemanticBulkSearchAPI(BaseSearchEngine):
    """
    A tool for searching literatures on Semantic Scholar.
    Inherits from BaseSearchEngine to provide unified interface.
    """
    base_url: str = "https://api.semanticscholar.org/graph/v1/paper/search/bulk?"
    switch_grammar = {
        "AND": '+',
        "OR": '|',
        "NOT": '-',
    }
    
    def get_source_name(self) -> str:
        """Get the name of the data source."""
        return "semantic_scholar"

    def validate_params(self, query: str, **kwargs) -> bool:
        """
        Validate search parameters for Semantic Scholar.
        
        Extends base validation with Semantic Scholar specific checks.
        """
        # Call base validation first
        if not super().validate_params(query, **kwargs):
            return False
        
        # Validate document_type
        document_type = kwargs.get('document_type', '')
        if document_type:
            try:
                document_type_to_semantic(document_type)
            except ValueError as e:
                self.logger.error(f"Invalid document type: {e}")
                return False
        
        # Validate fields_of_study
        fields_of_study = kwargs.get('fields_of_study')
        if fields_of_study is not None and not isinstance(fields_of_study, str):
            self.logger.error(f"fields_of_study must be a string, got: {type(fields_of_study)}")
            return False
        
        # Validate fields parameter
        fields = kwargs.get('fields')
        if fields is not None and not isinstance(fields, str):
            self.logger.error(f"fields must be a string, got: {type(fields)}")
            return False
        
        # Validate filtered parameter
        filtered = kwargs.get('filtered')
        if filtered is not None and not isinstance(filtered, bool):
            self.logger.error(f"filtered must be a boolean, got: {type(filtered)}")
            return False
        
        return True
    
    def check_query(self, query: str):
        """
        replace grammar in query
        """
        for key, value in self.switch_grammar.items():
            query = query.replace(key, value)
        return f"({query})"

    def query_once(self, query: str,
                   year: str = '',
                   document_type: str = '',
                   fields_of_study: str = '',
                   fields: str = '',
                   offset: int = 0,
                   limit: int = 100,
                   token: str = None,
                   filtered: bool = False) -> tuple[int, list, str, str]:
        """
        Query once for the semantic scholar bulk search.
        """
        # 构建基础 URL
        url = f"{self.base_url}query={query}"

        # 添加年份过滤
        if year:
            url += f"&year={year}"

        # 添加文档类型过滤    
        if document_type:
            url += f"&publicationTypes={document_type}"

        # 添加学科领域过滤    
        if fields_of_study:
            url += f"&fieldsOfStudy={fields_of_study}"

        # 添加返回字段限制    
        if fields:
            url += f"&fields={fields}"

        # 添加分页 token    
        if token:
            url += f"&token={token}"

        url += f"&offset={offset}&limit={limit}"

        logger.debug(f"Semantic Scholar bulk search request: {url}")

        try:
            response = requests.get(url, timeout=30)  # 添加超时限制
            if response.status_code != 200:
                logger.error(f"Semantic Scholar API request failed: {response.status_code}")
                return 0, [], url, ''

            response = response.json()
            total = response.get('total', 0)
            data = response.get('data', [])
            next_token = response.get('token')

            if filtered:
                data = [paper for paper in data if paper and
                        ('abstract' not in fields or paper.get('abstract'))]

            logger.debug(f"Semantic Scholar bulk search response: total={total}, data_length={len(data)}")
            return total, data, url, next_token

        except requests.Timeout:
            logger.error("Semantic Scholar API request timeout")
            return 0, [], url, ''
        except Exception as e:
            logger.error(f"Semantic Scholar API request error: {e}")
            traceback.print_exc()
            return 0, [], url, ''

    def query(self, query: str,
              year: str = '',
              document_type: str = '',
              fields_of_study: str = '',
              fields: str = '',
              num_results: int = 50,
              filtered: bool = False) -> tuple[list[dict], dict]:
        """
        Paper bulk search on Semantic Scholar.
        """
        query = self.check_query(query)
        document_type = document_type_to_semantic(document_type)
        fields = SemanticScholarPaper.get_fields(fields)
        limit = min(num_results, 1000)

        # 初始查询
        total, data, url, token = self.query_once(query, year, document_type, fields_of_study, fields, filtered=filtered, limit=limit)

        logger.debug(f"Semantic Scholar bulk search: {url} success. Total: {total}")

        metadata = {
            "total": total,
            "url": url,
            "token": token,
            "query": query,
        }

        if total == 0:
            return [], metadata

        result = data
        # 如果需要更多结果且有下一页，继续获取
        max_attempts = min(num_results // 1000 + 1, 10)  # 限制最大请求次数
        attempts = 1

        while token and len(result) < num_results and attempts < max_attempts:
            time.sleep(1)  # 添加短暂延迟避免请求过快
            attempts += 1
            limit = min(num_results - len(result), 1000)

            total, data, url, token = self.query_once(
                query, year, document_type, fields_of_study, fields,
                offset=len(result), limit=limit, token=token, filtered=filtered,
            )
            if not data:
                break
            result.extend(data)
            logger.debug(f"Retrieved {len(result)} results after {attempts} attempts")

        # 截取所需数量的结果
        result = result[:num_results]
        logger.debug(f"Final results: {len(result)}")
        return result, metadata

    def _search(self, query: str, **kwargs) -> Tuple[List[Dict], Dict]:
        """
        Execute raw search against Semantic Scholar API.
        
        Args:
            query: Search query string
            **kwargs: Additional search parameters including:
                - year: Year range filter
                - document_type: Document type filter
                - fields_of_study: Fields of study filter
                - fields: Fields to return
                - num_results: Number of results to return
                - filtered: Whether to filter results
                
        Returns:
            Tuple[List[Dict], Dict]: Raw results and metadata
        """
        # Extract parameters with defaults
        year = kwargs.get('year', '')
        document_type = kwargs.get('document_type', '')
        fields_of_study = kwargs.get('fields_of_study', '')
        fields = kwargs.get('fields', '')
        num_results = kwargs.get('num_results', 50)
        filtered = kwargs.get('filtered', False)
        
        if not num_results:
            return [], {}
            
        try:
            result, metadata = self.query(query, year, document_type, fields_of_study, fields, num_results, filtered)
            self.logger.debug(f"semantic_bulk_search result num: {len(result)}")
            return result, metadata
        except Exception as e:
            self.logger.error(f"Error in Semantic Scholar search: {e}")
            raise NetworkError(f"Semantic Scholar search failed: {e}")
    
    def _response_format(self, results: List[Dict]) -> List[Dict]:
        """
        Format raw Semantic Scholar results into LiteratureSchema format.
        
        Args:
            results: Raw search results from Semantic Scholar API
            
        Returns:
            List[Dict]: Formatted results conforming to LiteratureSchema
        """
        return SemanticResultFormatter().response_format(results)