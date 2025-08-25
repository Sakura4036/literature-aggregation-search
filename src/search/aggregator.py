"""
搜索聚合器 - 统一管理多数据源搜索

实现并行搜索、结果聚合、去重合并等核心功能
支持新的BaseSearchEngine架构和LiteratureSchema格式
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple, Any

from .engine import *
from ..models.enums import IdentifierType

logger = logging.getLogger(__name__)


class SearchProgress:
    """搜索进度跟踪"""
    
    def __init__(self, total_sources: int):
        self.total_sources = total_sources
        self.completed_sources = 0
        self.failed_sources = 0
        self.results_count = 0
        self.start_time = time.time()
        self.source_status = {}
    
    def update_source_status(self, source: str, status: str, count: int = 0, error: str = None):
        """更新数据源状态"""
        self.source_status[source] = {
            'status': status,  # 'searching', 'completed', 'failed'
            'count': count,
            'error': error,
            'timestamp': time.time()
        }
        
        if status == 'completed':
            self.completed_sources += 1
            self.results_count += count
        elif status == 'failed':
            self.failed_sources += 1
    
    def get_progress(self) -> Dict[str, Any]:
        """获取当前进度"""
        elapsed_time = time.time() - self.start_time
        return {
            'total_sources': self.total_sources,
            'completed_sources': self.completed_sources,
            'failed_sources': self.failed_sources,
            'results_count': self.results_count,
            'elapsed_time': elapsed_time,
            'source_status': self.source_status,
            'progress_percentage': (self.completed_sources + self.failed_sources) / self.total_sources * 100
        }


class SearchAggregator:
    """搜索聚合器 - 统一管理多数据源搜索"""
    
    def __init__(self):
        """初始化搜索聚合器"""
        self.search_apis = {
            'pubmed': PubmedSearchAPI(),
            'arxiv': ArxivSearchAPI(),
            'biorxiv': BioRxivSearchAPI(),
            'semantic_scholar': SemanticBulkSearchAPI(),
            'wos': WosSearchAPI(),
        }
        self.max_workers = 4  # 并发搜索的最大线程数
        
        # 验证所有API都继承自BaseSearchEngine
        for source, api in self.search_apis.items():
            if not isinstance(api, BaseSearchEngine):
                logger.warning(f"API {source} does not inherit from BaseSearchEngine")
        
        logger.info(f"SearchAggregator initialized with {len(self.search_apis)} search engines")
    
    def search_single_source(self, source: str, query: str, **kwargs) -> Tuple[str, List[Dict], Dict, Optional[str]]:
        """搜索单个数据源
        
        Args:
            source: 数据源名称
            query: 搜索查询
            **kwargs: 搜索参数
            
        Returns:
            Tuple[source, results, metadata, error]
        """
        try:
            if source not in self.search_apis:
                return source, [], {}, f"Unsupported source: {source}"
            
            api = self.search_apis[source]
            
            # 调用统一的search方法（所有API都应该继承BaseSearchEngine）
            if hasattr(api, 'search'):
                results, metadata = api.search(query, **kwargs)
                
                # 验证结果格式 - 应该是LiteratureSchema格式的字典列表
                if results and isinstance(results, list):
                    # 验证第一个结果是否符合预期格式
                    first_result = results[0]
                    if isinstance(first_result, dict):
                        # 检查是否包含LiteratureSchema的关键字段
                        expected_fields = ['article', 'authors', 'venue', 'identifiers']
                        if not all(field in first_result for field in expected_fields):
                            logger.warning(f"Results from {source} may not be in LiteratureSchema format")
                    
                logger.info(f"Successfully searched {source}: {len(results)} results")
                return source, results, metadata, None
            else:
                return source, [], {}, f"Search method not found for {source}"
            
        except Exception as e:
            error_msg = f"Error searching {source}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return source, [], {}, error_msg
    
    def search_all_sources(self, query: str, sources: Optional[List[str]] = None, 
                          progress_callback: Optional[callable] = None, **kwargs) -> Dict[str, Any]:
        """并行搜索所有或指定的数据源
        
        Args:
            query: 搜索查询
            sources: 指定要搜索的数据源列表，None表示搜索所有
            progress_callback: 进度回调函数
            **kwargs: 搜索参数
            
        Returns:
            Dict包含搜索结果和元数据
        """
        # 确定要搜索的数据源
        if sources is None:
            sources = list(self.search_apis.keys())
        else:
            # 验证数据源是否支持
            sources = [s for s in sources if s in self.search_apis]
        
        if not sources:
            return {
                'results': [],
                'metadata': {
                    'total_results': 0,
                    'sources_searched': [],
                    'search_time': 0,
                    'errors': ['No valid sources specified']
                }
            }
        
        # 初始化进度跟踪
        progress = SearchProgress(len(sources))
        
        # 并行搜索
        all_results = []
        source_metadata = {}
        errors = []
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交搜索任务
            future_to_source = {}
            for source in sources:
                progress.update_source_status(source, 'searching')
                if progress_callback:
                    progress_callback(progress.get_progress())
                
                future = executor.submit(self.search_single_source, source, query, **kwargs)
                future_to_source[future] = source
            
            # 收集结果
            for future in as_completed(future_to_source):
                source = future_to_source[future]
                try:
                    source_name, results, metadata, error = future.result()
                    
                    if error:
                        errors.append(f"{source_name}: {error}")
                        progress.update_source_status(source_name, 'failed', error=error)
                    else:
                        all_results.extend(results)
                        source_metadata[source_name] = metadata
                        progress.update_source_status(source_name, 'completed', len(results))
                    
                    # 调用进度回调
                    if progress_callback:
                        progress_callback(progress.get_progress())
                        
                except Exception as e:
                    error_msg = f"Unexpected error for {source}: {str(e)}"
                    errors.append(error_msg)
                    progress.update_source_status(source, 'failed', error=error_msg)
                    logger.error(error_msg)
        
        search_time = time.time() - start_time
        
        # 构建返回结果
        result = {
            'results': all_results,
            'metadata': {
                'total_results': len(all_results),
                'sources_searched': list(source_metadata.keys()),
                'search_time': search_time,
                'source_metadata': source_metadata,
                'progress': progress.get_progress(),
                'errors': errors
            }
        }
        
        logger.info(f"Search completed: {len(all_results)} total results from {len(source_metadata)} sources in {search_time:.2f}s")
        
        return result
    
    def search_with_deduplication(self, query: str, sources: Optional[List[str]] = None,
                                 deduplicate: bool = True, **kwargs) -> Dict[str, Any]:
        """搜索并去重
        
        Args:
            query: 搜索查询
            sources: 数据源列表
            deduplicate: 是否进行去重
            **kwargs: 搜索参数
            
        Returns:
            Dict包含去重后的结果
        """
        # 执行搜索
        search_result = self.search_all_sources(query, sources, **kwargs)
        
        if not deduplicate or not search_result['results']:
            return search_result
        
        # 使用新的标识符系统进行去重
        try:
            original_count = len(search_result['results'])
            deduplicated_results = self._deduplicate_literature_schema(search_result['results'])
            duplicates_removed = original_count - len(deduplicated_results)
            
            # 更新结果
            search_result['results'] = deduplicated_results
            search_result['metadata']['total_results'] = len(deduplicated_results)
            search_result['metadata']['duplicates_removed'] = duplicates_removed
            search_result['metadata']['deduplication_enabled'] = True
            
            logger.info(f"Deduplication completed: removed {duplicates_removed} duplicates")
            
        except Exception as e:
            logger.error(f"Deduplication failed: {e}")
            search_result['metadata']['deduplication_enabled'] = False
            search_result['metadata']['deduplication_error'] = str(e)
        
        return search_result
    
    def _deduplicate_literature_schema(self, results: List[Dict]) -> List[Dict]:
        """使用新的标识符系统对LiteratureSchema格式的结果进行去重
        
        Args:
            results: LiteratureSchema格式的结果列表
            
        Returns:
            去重后的结果列表
        """
        if not results:
            return []
        
        # 标识符优先级（从高到低）
        identifier_priority = [
            IdentifierType.DOI,
            IdentifierType.PMID,
            IdentifierType.ARXIV_ID,
            IdentifierType.SEMANTIC_SCHOLAR_ID,
            IdentifierType.WOS_UID
        ]
        
        unique_results = []
        seen_identifiers = {}  # identifier_key -> result_index
        
        for result in results:
            is_duplicate = False
            duplicate_of_index = None
            
            # 检查标识符是否已存在
            if 'identifiers' in result and isinstance(result['identifiers'], list):
                for identifier in result['identifiers']:
                    if isinstance(identifier, dict):
                        id_type_str = identifier.get('identifier_type')
                        id_value = identifier.get('identifier_value')
                        
                        if id_type_str and id_value:
                            # 转换字符串为枚举类型
                            try:
                                if isinstance(id_type_str, str):
                                    id_type = IdentifierType(id_type_str)
                                else:
                                    id_type = id_type_str
                                
                                if id_type in identifier_priority:
                                    normalized_value = self._normalize_identifier_value(id_type, id_value)
                                    identifier_key = f"{id_type.value}:{normalized_value}"
                                    
                                    if identifier_key in seen_identifiers:
                                        is_duplicate = True
                                        duplicate_of_index = seen_identifiers[identifier_key]
                                        break
                            except ValueError:
                                # 未知的标识符类型，跳过
                                continue
            
            if is_duplicate and duplicate_of_index is not None:
                # 合并重复结果
                unique_results[duplicate_of_index] = self._merge_literature_results(
                    unique_results[duplicate_of_index], result
                )
            else:
                # 记录所有标识符
                if 'identifiers' in result and isinstance(result['identifiers'], list):
                    for identifier in result['identifiers']:
                        if isinstance(identifier, dict):
                            id_type_str = identifier.get('identifier_type')
                            id_value = identifier.get('identifier_value')
                            
                            if id_type_str and id_value:
                                try:
                                    if isinstance(id_type_str, str):
                                        id_type = IdentifierType(id_type_str)
                                    else:
                                        id_type = id_type_str
                                    
                                    if id_type in identifier_priority:
                                        normalized_value = self._normalize_identifier_value(id_type, id_value)
                                        identifier_key = f"{id_type.value}:{normalized_value}"
                                        seen_identifiers[identifier_key] = len(unique_results)
                                except ValueError:
                                    continue
                
                unique_results.append(result)
        
        return unique_results
    
    def _normalize_identifier_value(self, identifier_type: IdentifierType, value: str) -> str:
        """标准化标识符值
        
        Args:
            identifier_type: 标识符类型
            value: 标识符值
            
        Returns:
            标准化后的值
        """
        if not value:
            return ""
        
        normalized = str(value).strip().lower()
        
        if identifier_type == IdentifierType.DOI:
            # 移除DOI前缀
            import re
            normalized = re.sub(r'^(doi:|https?://doi\.org/|https?://dx\.doi\.org/)', '', normalized)
            normalized = normalized.strip('/')
        elif identifier_type == IdentifierType.PMID:
            # 确保是纯数字
            import re
            normalized = re.sub(r'[^\d]', '', normalized)
        elif identifier_type == IdentifierType.ARXIV_ID:
            # 标准化ArXiv ID格式
            import re
            normalized = re.sub(r'^arxiv:', '', normalized)
            normalized = re.sub(r'v\d+$', '', normalized)  # 移除版本号
        
        return normalized
    
    def _merge_literature_results(self, result1: Dict, result2: Dict) -> Dict:
        """合并两个LiteratureSchema格式的结果
        
        Args:
            result1: 第一个结果
            result2: 第二个结果
            
        Returns:
            合并后的结果
        """
        # 选择更完整的结果作为基础
        base_result = self._select_more_complete_result(result1, result2)
        merged_result = base_result.copy()
        
        # 合并标识符
        all_identifiers = []
        for result in [result1, result2]:
            if 'identifiers' in result and isinstance(result['identifiers'], list):
                all_identifiers.extend(result['identifiers'])
        
        # 去重标识符
        unique_identifiers = []
        seen_identifier_keys = set()
        for identifier in all_identifiers:
            if isinstance(identifier, dict):
                id_type = identifier.get('identifier_type')
                id_value = identifier.get('identifier_value')
                if id_type and id_value:
                    key = f"{id_type}:{id_value}"
                    if key not in seen_identifier_keys:
                        unique_identifiers.append(identifier)
                        seen_identifier_keys.add(key)
        
        merged_result['identifiers'] = unique_identifiers
        
        # 合并数据源信息
        sources = []
        for result in [result1, result2]:
            if 'source_specific' in result and 'source' in result['source_specific']:
                source = result['source_specific']['source']
                if source not in sources:
                    sources.append(source)
        
        # 更新source_specific信息
        if 'source_specific' not in merged_result:
            merged_result['source_specific'] = {}
        
        merged_result['source_specific']['merged_from_sources'] = sources
        merged_result['source_specific']['merge_count'] = 2
        
        # 合并引用计数（取最大值）
        if 'article' in merged_result and 'article' in result2:
            article1 = merged_result['article']
            article2 = result2['article']
            
            # 取更大的引用数
            if article2.get('citation_count', 0) > article1.get('citation_count', 0):
                article1['citation_count'] = article2['citation_count']
            
            if article2.get('reference_count', 0) > article1.get('reference_count', 0):
                article1['reference_count'] = article2['reference_count']
        
        return merged_result
    
    def _select_more_complete_result(self, result1: Dict, result2: Dict) -> Dict:
        """选择更完整的结果
        
        Args:
            result1: 结果1
            result2: 结果2
            
        Returns:
            更完整的结果
        """
        def completeness_score(result):
            score = 0
            
            # 文章信息完整性
            if 'article' in result:
                article = result['article']
                if article.get('title'): score += 10
                if article.get('abstract'): score += 8
                if article.get('publication_date'): score += 5
                if article.get('citation_count', 0) > 0: score += 3
            
            # 作者信息完整性
            if 'authors' in result and isinstance(result['authors'], list):
                score += min(len(result['authors']) * 2, 10)
            
            # 标识符完整性
            if 'identifiers' in result and isinstance(result['identifiers'], list):
                score += min(len(result['identifiers']) * 3, 15)
            
            # 场所信息完整性
            if 'venue' in result and result['venue'].get('venue_name'):
                score += 5
            
            return score
        
        score1 = completeness_score(result1)
        score2 = completeness_score(result2)
        
        return result1 if score1 >= score2 else result2

    def get_supported_sources(self) -> List[str]:
        """获取支持的数据源列表"""
        return list(self.search_apis.keys())
    
    def validate_search_params(self, query: str, sources: Optional[List[str]] = None, **kwargs) -> Tuple[bool, List[str]]:
        """验证搜索参数
        
        Returns:
            Tuple[is_valid, error_messages]
        """
        errors = []
        
        # 验证查询字符串
        if not query or not query.strip():
            errors.append("Query cannot be empty")
        
        # 验证数据源
        if sources:
            invalid_sources = [s for s in sources if s not in self.search_apis]
            if invalid_sources:
                errors.append(f"Unsupported sources: {invalid_sources}")
        
        # 验证数量限制
        num_results = kwargs.get('num_results', 50)
        if not isinstance(num_results, int) or num_results <= 0:
            errors.append("num_results must be a positive integer")
        elif num_results > 10000:
            errors.append("num_results cannot exceed 10000")
        
        return len(errors) == 0, errors


# 便捷函数
def search_literature(query: str, sources: Optional[List[str]] = None, 
                     deduplicate: bool = True, progress_callback: Optional[callable] = None,
                     **kwargs) -> Dict[str, Any]:
    """便捷的文献搜索函数
    
    Args:
        query: 搜索查询
        sources: 数据源列表，None表示搜索所有
        deduplicate: 是否去重
        progress_callback: 进度回调函数
        **kwargs: 其他搜索参数
        
    Returns:
        搜索结果字典
    """
    aggregator = SearchAggregator()
    
    # 验证参数
    is_valid, errors = aggregator.validate_search_params(query, sources, **kwargs)
    if not is_valid:
        return {
            'results': [],
            'metadata': {
                'total_results': 0,
                'sources_searched': [],
                'search_time': 0,
                'errors': errors
            }
        }
    
    # 执行搜索
    return aggregator.search_with_deduplication(
        query=query,
        sources=sources,
        deduplicate=deduplicate,
        progress_callback=progress_callback,
        **kwargs
    )


if __name__ == "__main__":
    # 测试搜索聚合器
    def progress_callback(progress):
        print(f"Progress: {progress['progress_percentage']:.1f}% - {progress['completed_sources']}/{progress['total_sources']} sources completed")
    
    # 测试搜索
    results = search_literature(
        query="synthetic biology",
        sources=['pubmed', 'arxiv'],
        num_results=10,
        progress_callback=progress_callback
    )
    
    print(f"\nSearch completed:")
    print(f"Total results: {results['metadata']['total_results']}")
    print(f"Sources: {results['metadata']['sources_searched']}")
    print(f"Search time: {results['metadata']['search_time']:.2f}s")
    
    if results['metadata'].get('errors'):
        print(f"Errors: {results['metadata']['errors']}")