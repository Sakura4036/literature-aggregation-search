"""
数据合并器 - 合并来自不同数据源的同一文献信息

实现智能的字段合并策略和数据质量评估
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DataMerger:
    """数据合并器 - 合并重复文献的信息"""
    
    # 数据源优先级（用于字段冲突解决）
    SOURCE_PRIORITY = {
        'pubmed': 10,      # PubMed权威性最高
        'semantic_scholar': 8,  # Semantic Scholar数据完整
        'arxiv': 6,        # ArXiv预印本权威
        'biorxiv': 5,      # bioRxiv生物预印本
        'wos': 7,          # Web of Science引文权威
    }
    
    # 字段合并策略
    FIELD_MERGE_STRATEGIES = {
        'title': 'longest',           # 选择最长的标题
        'abstract': 'longest',        # 选择最长的摘要
        'publication_date': 'earliest',  # 选择最早的发表日期
        'citation_count': 'max',      # 选择最大的引用数
        'reference_count': 'max',     # 选择最大的参考文献数
        'is_open_access': 'any_true', # 任一为真则为真
        'publication_year': 'earliest', # 选择最早的年份
    }
    
    def __init__(self):
        """初始化数据合并器"""
        self.merge_stats = {
            'articles_merged': 0,
            'fields_merged': 0,
            'conflicts_resolved': 0
        }
    
    def merge_articles(self, duplicates: List[Dict]) -> Dict:
        """合并重复文献的信息
        
        Args:
            duplicates: 重复文献列表
            
        Returns:
            合并后的文献信息
        """
        if not duplicates:
            return {}
        
        if len(duplicates) == 1:
            return duplicates[0]
        
        logger.info(f"Merging {len(duplicates)} duplicate articles")
        
        # 选择主要文献作为合并基础
        primary_article = self._select_primary_article(duplicates)
        merged_article = primary_article.copy()
        
        # 合并各个部分
        merged_article['article'] = self._merge_article_section(
            [article.get('article', {}) for article in duplicates]
        )
        
        merged_article['authors'] = self._merge_authors(
            [article.get('authors', []) for article in duplicates]
        )
        
        merged_article['venue'] = self._merge_venue_info(
            [article.get('venue', {}) for article in duplicates]
        )
        
        merged_article['identifiers'] = self._merge_identifiers(
            [article.get('identifiers', []) for article in duplicates]
        )
        
        merged_article['publication_types'] = self._merge_publication_types(
            [article.get('publication_types', []) for article in duplicates]
        )
        
        # 添加合并元数据
        merged_article['merge_metadata'] = self._create_merge_metadata(duplicates)
        
        self.merge_stats['articles_merged'] += 1
        
        return merged_article
    
    def _select_primary_article(self, articles: List[Dict]) -> Dict:
        """选择主要文献作为合并基础
        
        选择标准：
        1. 数据源优先级
        2. 信息完整度
        3. 数据质量
        
        Args:
            articles: 文献列表
            
        Returns:
            主要文献
        """
        def article_score(article):
            score = 0
            
            # 数据源优先级
            source = article.get('source_specific', {}).get('source', '')
            score += self.SOURCE_PRIORITY.get(source, 0) * 10
            
            # 信息完整度
            article_data = article.get('article', {})
            if article_data.get('title'): score += 5
            if article_data.get('abstract'): score += 8
            if article_data.get('publication_date'): score += 3
            
            # 作者信息
            authors = article.get('authors', [])
            score += min(len(authors), 5) * 2
            
            # 标识符数量
            identifiers = article.get('identifiers', [])
            score += min(len(identifiers), 3) * 3
            
            # 引用信息
            if article_data.get('citation_count'): score += 2
            
            return score
        
        return max(articles, key=article_score)
    
    def _merge_article_section(self, article_sections: List[Dict]) -> Dict:
        """合并文章基本信息部分
        
        Args:
            article_sections: 文章信息列表
            
        Returns:
            合并后的文章信息
        """
        merged = {}
        
        for field in ['title', 'abstract', 'publication_date', 'publication_year', 
                     'citation_count', 'reference_count', 'is_open_access', 'open_access_url']:
            values = [section.get(field) for section in article_sections if section.get(field)]
            if values:
                merged[field] = self._select_best_field_value(field, values)
        
        return merged
    
    def _merge_authors(self, author_lists: List[List[Dict]]) -> List[Dict]:
        """合并作者信息
        
        Args:
            author_lists: 作者列表的列表
            
        Returns:
            合并后的作者列表
        """
        # 选择最完整的作者列表
        if not author_lists:
            return []
        
        # 按作者数量和信息完整度排序
        def author_list_score(authors):
            if not authors:
                return 0
            
            score = len(authors) * 10
            
            # 加分项：作者信息完整度
            for author in authors:
                if isinstance(author, dict):
                    if author.get('full_name'): score += 2
                    if author.get('affiliation'): score += 1
                elif isinstance(author, str) and author.strip():
                    score += 1
            
            return score
        
        best_authors = max(author_lists, key=author_list_score)
        return best_authors
    
    def _merge_venue_info(self, venue_infos: List[Dict]) -> Dict:
        """合并期刊/会议信息
        
        Args:
            venue_infos: 期刊信息列表
            
        Returns:
            合并后的期刊信息
        """
        merged = {}
        
        for field in ['venue_name', 'venue_type', 'issn_print', 'issn_electronic', 'publisher']:
            values = [venue.get(field) for venue in venue_infos if venue.get(field)]
            if values:
                merged[field] = self._select_best_field_value(field, values)
        
        return merged
    
    def _merge_identifiers(self, identifier_lists: List[List[Dict]]) -> List[Dict]:
        """合并标识符信息
        
        Args:
            identifier_lists: 标识符列表的列表
            
        Returns:
            合并后的标识符列表
        """
        all_identifiers = []
        seen_identifiers = set()
        
        for identifier_list in identifier_lists:
            for identifier in identifier_list:
                if isinstance(identifier, dict):
                    id_type = identifier.get('identifier_type')
                    id_value = identifier.get('identifier_value')
                    
                    if id_type and id_value:
                        # 标准化标识符用于去重
                        normalized_key = f"{id_type}:{str(id_value).strip().lower()}"
                        
                        if normalized_key not in seen_identifiers:
                            all_identifiers.append(identifier)
                            seen_identifiers.add(normalized_key)
        
        return all_identifiers
    
    def _merge_publication_types(self, type_lists: List[List[Dict]]) -> List[Dict]:
        """合并发表类型信息
        
        Args:
            type_lists: 发表类型列表的列表
            
        Returns:
            合并后的发表类型列表
        """
        all_types = []
        seen_types = set()
        
        for type_list in type_lists:
            for pub_type in type_list:
                if isinstance(pub_type, dict):
                    type_name = pub_type.get('type_name', '').strip()
                    if type_name and type_name.lower() not in seen_types:
                        all_types.append(pub_type)
                        seen_types.add(type_name.lower())
        
        return all_types
    
    def _select_best_field_value(self, field_name: str, values: List[Any]) -> Any:
        """选择最佳字段值
        
        Args:
            field_name: 字段名
            values: 候选值列表
            
        Returns:
            最佳值
        """
        if not values:
            return None
        
        # 过滤空值
        non_empty_values = [v for v in values if v is not None and str(v).strip()]
        if not non_empty_values:
            return None
        
        strategy = self.FIELD_MERGE_STRATEGIES.get(field_name, 'first')
        
        if strategy == 'longest':
            return max(non_empty_values, key=lambda x: len(str(x)))
        
        elif strategy == 'shortest':
            return min(non_empty_values, key=lambda x: len(str(x)))
        
        elif strategy == 'max':
            numeric_values = [v for v in non_empty_values if isinstance(v, (int, float))]
            return max(numeric_values) if numeric_values else non_empty_values[0]
        
        elif strategy == 'min':
            numeric_values = [v for v in non_empty_values if isinstance(v, (int, float))]
            return min(numeric_values) if numeric_values else non_empty_values[0]
        
        elif strategy == 'earliest':
            # 对于日期字段
            if field_name in ['publication_date', 'publication_year']:
                try:
                    if field_name == 'publication_year':
                        year_values = [int(v) for v in non_empty_values if str(v).isdigit()]
                        return min(year_values) if year_values else non_empty_values[0]
                    else:
                        # 处理日期字符串
                        date_values = []
                        for v in non_empty_values:
                            try:
                                if isinstance(v, str):
                                    # 尝试解析不同的日期格式
                                    for fmt in ['%Y-%m-%d', '%Y-%m', '%Y']:
                                        try:
                                            date_obj = datetime.strptime(v, fmt)
                                            date_values.append((date_obj, v))
                                            break
                                        except ValueError:
                                            continue
                            except:
                                continue
                        
                        if date_values:
                            return min(date_values, key=lambda x: x[0])[1]
                except:
                    pass
            
            return non_empty_values[0]
        
        elif strategy == 'latest':
            # 类似earliest但选择最新的
            if field_name in ['publication_date', 'publication_year']:
                try:
                    if field_name == 'publication_year':
                        year_values = [int(v) for v in non_empty_values if str(v).isdigit()]
                        return max(year_values) if year_values else non_empty_values[0]
                except:
                    pass
            
            return non_empty_values[-1]
        
        elif strategy == 'any_true':
            # 对于布尔字段，任一为真则为真
            bool_values = [bool(v) for v in non_empty_values]
            return any(bool_values)
        
        elif strategy == 'all_true':
            # 对于布尔字段，全部为真才为真
            bool_values = [bool(v) for v in non_empty_values]
            return all(bool_values)
        
        else:  # 'first' or unknown strategy
            return non_empty_values[0]
    
    def _create_merge_metadata(self, articles: List[Dict]) -> Dict:
        """创建合并元数据
        
        Args:
            articles: 原始文章列表
            
        Returns:
            合并元数据
        """
        sources = []
        source_counts = {}
        
        for article in articles:
            source = article.get('source_specific', {}).get('source', 'unknown')
            if source not in sources:
                sources.append(source)
            source_counts[source] = source_counts.get(source, 0) + 1
        
        return {
            'merged_from_sources': sources,
            'source_counts': source_counts,
            'total_duplicates': len(articles),
            'merge_timestamp': datetime.now().isoformat(),
            'primary_source': articles[0].get('source_specific', {}).get('source', 'unknown')
        }
    
    def get_merge_stats(self) -> Dict[str, int]:
        """获取合并统计信息
        
        Returns:
            统计信息字典
        """
        return self.merge_stats.copy()
    
    def reset_stats(self):
        """重置统计信息"""
        self.merge_stats = {
            'articles_merged': 0,
            'fields_merged': 0,
            'conflicts_resolved': 0
        }


if __name__ == "__main__":
    # 测试数据合并功能
    test_articles = [
        {
            'article': {
                'title': 'Short Title',
                'abstract': 'Short abstract',
                'publication_year': 2023,
                'citation_count': 10
            },
            'authors': [{'full_name': 'John Doe'}],
            'identifiers': [{'identifier_type': 'doi', 'identifier_value': '10.1000/test1'}],
            'source_specific': {'source': 'pubmed'}
        },
        {
            'article': {
                'title': 'Much Longer and More Detailed Title',
                'abstract': 'This is a much longer and more detailed abstract with more information',
                'publication_year': 2022,
                'citation_count': 15
            },
            'authors': [{'full_name': 'John Doe'}, {'full_name': 'Jane Smith'}],
            'identifiers': [
                {'identifier_type': 'doi', 'identifier_value': '10.1000/test1'},
                {'identifier_type': 'pmid', 'identifier_value': '12345'}
            ],
            'source_specific': {'source': 'semantic_scholar'}
        }
    ]
    
    merger = DataMerger()
    merged_article = merger.merge_articles(test_articles)
    
    print("Merged article:")
    print(f"Title: {merged_article['article']['title']}")
    print(f"Abstract length: {len(merged_article['article']['abstract'])}")
    print(f"Publication year: {merged_article['article']['publication_year']}")
    print(f"Citation count: {merged_article['article']['citation_count']}")
    print(f"Authors: {len(merged_article['authors'])}")
    print(f"Identifiers: {len(merged_article['identifiers'])}")
    print(f"Merged from sources: {merged_article['merge_metadata']['merged_from_sources']}")
    print(f"Stats: {merger.get_merge_stats()}")