"""
搜索聚合器 - 统一管理多数据源搜索

实现并行搜索、结果聚合、去重合并等核心功能
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from .pubmed_search import PubmedSearchAPI
from .arxiv_search import ArxivSearchAPI
from .biorxiv_search import BioRxivSearchAPI
from .semantic_search import SemanticBulkSearchAPI
from .response_formatter import ResponseFormatter

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
            # 'wos': WosSearchAPI(),  # 待实现
        }
        self.formatter = ResponseFormatter()
        self.max_workers = 4  # 并发搜索的最大线程数
    
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
            
            # 根据不同API调用相应的搜索方法
            if hasattr(api, 'search'):
                results, metadata = api.search(query, **kwargs)
            else:
                return source, [], {}, f"Search method not found for {source}"
            
            logger.info(f"Successfully searched {source}: {len(results)} results")
            return source, results, metadata, None
            
        except Exception as e:
            error_msg = f"Error searching {source}: {str(e)}"
            logger.error(error_msg)
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
        
        # 导入去重模块（避免循环导入）
        try:
            from ..processing.deduplicator import Deduplicator
            deduplicator = Deduplicator()
            
            # 执行去重
            original_count = len(search_result['results'])
            deduplicated_results = deduplicator.deduplicate(search_result['results'])
            duplicates_removed = original_count - len(deduplicated_results)
            
            # 更新结果
            search_result['results'] = deduplicated_results
            search_result['metadata']['total_results'] = len(deduplicated_results)
            search_result['metadata']['duplicates_removed'] = duplicates_removed
            search_result['metadata']['deduplication_enabled'] = True
            
            logger.info(f"Deduplication completed: removed {duplicates_removed} duplicates")
            
        except ImportError:
            logger.warning("Deduplicator not available, skipping deduplication")
            search_result['metadata']['deduplication_enabled'] = False
        
        return search_result
    
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