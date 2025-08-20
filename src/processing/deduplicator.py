"""
文献去重处理器

实现基于多重标识符的智能去重算法
"""

import logging
from typing import Dict, List, Set, Tuple, Optional
from difflib import SequenceMatcher
import re

logger = logging.getLogger(__name__)


class Deduplicator:
    """文献去重处理器"""
    
    # 标识符优先级（从高到低）
    IDENTIFIER_PRIORITY = ['doi', 'pmid', 'arxiv_id', 'semantic_scholar_id', 'wos_uid']
    
    # 模糊匹配阈值
    TITLE_SIMILARITY_THRESHOLD = 0.85
    AUTHOR_SIMILARITY_THRESHOLD = 0.7
    
    def __init__(self):
        """初始化去重处理器"""
        self.stats = {
            'total_articles': 0,
            'duplicates_found': 0,
            'exact_matches': 0,
            'fuzzy_matches': 0,
            'unique_articles': 0
        }
    
    def deduplicate(self, articles: List[Dict]) -> List[Dict]:
        """主要去重方法
        
        Args:
            articles: 文章列表
            
        Returns:
            去重后的文章列表
        """
        if not articles:
            return []
        
        self.stats['total_articles'] = len(articles)
        logger.info(f"Starting deduplication for {len(articles)} articles")
        
        # 第一步：基于标识符的精确匹配去重
        unique_articles = self._deduplicate_by_identifiers(articles)
        self.stats['exact_matches'] = self.stats['total_articles'] - len(unique_articles)
        
        # 第二步：基于标题和作者的模糊匹配去重
        if len(unique_articles) > 1:
            unique_articles = self._deduplicate_by_fuzzy_match(unique_articles)
            self.stats['fuzzy_matches'] = self.stats['exact_matches'] + len(unique_articles) - self.stats['total_articles']
        
        self.stats['duplicates_found'] = self.stats['total_articles'] - len(unique_articles)
        self.stats['unique_articles'] = len(unique_articles)
        
        logger.info(f"Deduplication completed: {self.stats['duplicates_found']} duplicates removed, {len(unique_articles)} unique articles")
        
        return unique_articles
    
    def _deduplicate_by_identifiers(self, articles: List[Dict]) -> List[Dict]:
        """基于标识符的精确匹配去重
        
        Args:
            articles: 文章列表
            
        Returns:
            去重后的文章列表
        """
        seen_identifiers = {}  # identifier_value -> article_index
        unique_articles = []
        duplicate_groups = {}  # 存储重复文章组
        
        for i, article in enumerate(articles):
            identifiers = self._extract_identifiers(article)
            is_duplicate = False
            duplicate_of = None
            
            # 检查每个标识符是否已存在
            for identifier_type in self.IDENTIFIER_PRIORITY:
                if identifier_type in identifiers and identifiers[identifier_type]:
                    identifier_value = self._normalize_identifier(identifier_type, identifiers[identifier_type])
                    identifier_key = f"{identifier_type}:{identifier_value}"
                    
                    if identifier_key in seen_identifiers:
                        is_duplicate = True
                        duplicate_of = seen_identifiers[identifier_key]
                        break
            
            if is_duplicate:
                # 合并重复文章信息
                if duplicate_of not in duplicate_groups:
                    duplicate_groups[duplicate_of] = [articles[duplicate_of]]
                duplicate_groups[duplicate_of].append(article)
            else:
                # 记录所有标识符
                for identifier_type, identifier_value in identifiers.items():
                    if identifier_value:
                        normalized_value = self._normalize_identifier(identifier_type, identifier_value)
                        identifier_key = f"{identifier_type}:{normalized_value}"
                        seen_identifiers[identifier_key] = i
                
                unique_articles.append(article)
        
        # 合并重复文章的信息
        for original_index, duplicates in duplicate_groups.items():
            merged_article = self._merge_articles(duplicates)
            # 找到并更新原始文章
            for i, article in enumerate(unique_articles):
                if self._articles_match_by_identifier(article, duplicates[0]):
                    unique_articles[i] = merged_article
                    break
        
        return unique_articles
    
    def _deduplicate_by_fuzzy_match(self, articles: List[Dict]) -> List[Dict]:
        """基于标题和作者的模糊匹配去重
        
        Args:
            articles: 文章列表
            
        Returns:
            去重后的文章列表
        """
        unique_articles = []
        
        for article in articles:
            is_duplicate = False
            
            for existing_article in unique_articles:
                if self._fuzzy_match(article, existing_article):
                    # 合并文章信息
                    merged_article = self._merge_articles([existing_article, article])
                    # 替换现有文章
                    index = unique_articles.index(existing_article)
                    unique_articles[index] = merged_article
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_articles.append(article)
        
        return unique_articles
    
    def _extract_identifiers(self, article: Dict) -> Dict[str, str]:
        """提取文章的所有标识符
        
        Args:
            article: 文章字典
            
        Returns:
            标识符字典
        """
        identifiers = {}
        
        # 从不同位置提取标识符
        if 'identifiers' in article and isinstance(article['identifiers'], list):
            for identifier in article['identifiers']:
                if isinstance(identifier, dict):
                    id_type = identifier.get('identifier_type')
                    id_value = identifier.get('identifier_value')
                    if id_type and id_value:
                        identifiers[id_type] = id_value
        
        # 从顶级字段提取
        for field in ['doi', 'pmid', 'arxiv_id', 'semantic_scholar_id']:
            if field in article and article[field]:
                identifiers[field] = str(article[field])
        
        # 从source_specific中提取
        if 'source_specific' in article and 'raw' in article['source_specific']:
            raw_data = article['source_specific']['raw']
            if isinstance(raw_data, dict):
                # PubMed PMID
                if 'pmid' in raw_data:
                    identifiers['pmid'] = str(raw_data['pmid'])
                # ArXiv ID
                if 'arxiv_id' in raw_data:
                    identifiers['arxiv_id'] = str(raw_data['arxiv_id'])
                # Semantic Scholar Paper ID
                if 'paperId' in raw_data:
                    identifiers['semantic_scholar_id'] = str(raw_data['paperId'])
        
        return identifiers
    
    def _normalize_identifier(self, identifier_type: str, identifier_value: str) -> str:
        """标准化标识符格式
        
        Args:
            identifier_type: 标识符类型
            identifier_value: 标识符值
            
        Returns:
            标准化后的标识符值
        """
        if not identifier_value:
            return ""
        
        value = str(identifier_value).strip().lower()
        
        if identifier_type == 'doi':
            # 移除DOI前缀
            value = re.sub(r'^(doi:|https?://doi\.org/|https?://dx\.doi\.org/)', '', value)
            # 标准化格式
            value = value.strip('/')
        elif identifier_type == 'pmid':
            # 确保是纯数字
            value = re.sub(r'[^\d]', '', value)
        elif identifier_type == 'arxiv_id':
            # 标准化ArXiv ID格式
            value = re.sub(r'^arxiv:', '', value)
            value = re.sub(r'v\d+$', '', value)  # 移除版本号
        
        return value
    
    def _fuzzy_match(self, article1: Dict, article2: Dict) -> bool:
        """基于标题和作者的模糊匹配
        
        Args:
            article1: 文章1
            article2: 文章2
            
        Returns:
            是否匹配
        """
        # 标题相似度检查
        title1 = self._normalize_title(article1.get('article', {}).get('title', ''))
        title2 = self._normalize_title(article2.get('article', {}).get('title', ''))
        
        if not title1 or not title2:
            return False
        
        title_similarity = SequenceMatcher(None, title1, title2).ratio()
        
        if title_similarity < self.TITLE_SIMILARITY_THRESHOLD:
            return False
        
        # 作者相似度检查
        authors1 = self._extract_author_names(article1)
        authors2 = self._extract_author_names(article2)
        
        if not authors1 or not authors2:
            # 如果标题高度相似且缺少作者信息，认为可能是同一篇文章
            return title_similarity > 0.95
        
        author_similarity = self._calculate_author_similarity(authors1, authors2)
        
        # 综合判断
        return (title_similarity >= self.TITLE_SIMILARITY_THRESHOLD and 
                author_similarity >= self.AUTHOR_SIMILARITY_THRESHOLD)
    
    def _normalize_title(self, title: str) -> str:
        """标准化标题格式
        
        Args:
            title: 原始标题
            
        Returns:
            标准化后的标题
        """
        if not title:
            return ""
        
        # 转换为小写
        title = title.lower()
        
        # 移除标点符号和多余空格
        title = re.sub(r'[^\w\s]', ' ', title)
        title = re.sub(r'\s+', ' ', title)
        
        # 移除常见的停用词
        stop_words = {'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        words = [word for word in title.split() if word not in stop_words]
        
        return ' '.join(words).strip()
    
    def _extract_author_names(self, article: Dict) -> List[str]:
        """提取作者姓名列表
        
        Args:
            article: 文章字典
            
        Returns:
            作者姓名列表
        """
        authors = []
        
        # 从authors字段提取
        if 'authors' in article and isinstance(article['authors'], list):
            for author in article['authors']:
                if isinstance(author, dict):
                    name = author.get('full_name', '')
                elif isinstance(author, str):
                    name = author
                else:
                    continue
                
                if name:
                    authors.append(self._normalize_author_name(name))
        
        return authors
    
    def _normalize_author_name(self, name: str) -> str:
        """标准化作者姓名
        
        Args:
            name: 原始姓名
            
        Returns:
            标准化后的姓名
        """
        if not name:
            return ""
        
        # 移除多余空格和标点
        name = re.sub(r'[^\w\s\-]', ' ', name)
        name = re.sub(r'\s+', ' ', name)
        
        return name.strip().lower()
    
    def _calculate_author_similarity(self, authors1: List[str], authors2: List[str]) -> float:
        """计算作者列表相似度
        
        Args:
            authors1: 作者列表1
            authors2: 作者列表2
            
        Returns:
            相似度分数 (0-1)
        """
        if not authors1 or not authors2:
            return 0.0
        
        # 计算交集
        set1 = set(authors1)
        set2 = set(authors2)
        
        # 精确匹配
        exact_matches = len(set1.intersection(set2))
        
        # 模糊匹配
        fuzzy_matches = 0
        for author1 in authors1:
            for author2 in authors2:
                if author1 not in set2 and author2 not in set1:
                    similarity = SequenceMatcher(None, author1, author2).ratio()
                    if similarity > 0.8:  # 作者姓名模糊匹配阈值
                        fuzzy_matches += 1
                        break
        
        total_matches = exact_matches + fuzzy_matches
        total_authors = max(len(authors1), len(authors2))
        
        return total_matches / total_authors if total_authors > 0 else 0.0
    
    def _articles_match_by_identifier(self, article1: Dict, article2: Dict) -> bool:
        """检查两篇文章是否通过标识符匹配
        
        Args:
            article1: 文章1
            article2: 文章2
            
        Returns:
            是否匹配
        """
        identifiers1 = self._extract_identifiers(article1)
        identifiers2 = self._extract_identifiers(article2)
        
        for identifier_type in self.IDENTIFIER_PRIORITY:
            if (identifier_type in identifiers1 and identifier_type in identifiers2 and
                identifiers1[identifier_type] and identifiers2[identifier_type]):
                
                norm1 = self._normalize_identifier(identifier_type, identifiers1[identifier_type])
                norm2 = self._normalize_identifier(identifier_type, identifiers2[identifier_type])
                
                if norm1 == norm2:
                    return True
        
        return False
    
    def _merge_articles(self, articles: List[Dict]) -> Dict:
        """合并重复文章的信息
        
        Args:
            articles: 重复文章列表
            
        Returns:
            合并后的文章
        """
        if not articles:
            return {}
        
        if len(articles) == 1:
            return articles[0]
        
        # 选择最完整的文章作为基础
        base_article = self._select_most_complete_article(articles)
        merged_article = base_article.copy()
        
        # 合并标识符
        all_identifiers = []
        for article in articles:
            if 'identifiers' in article and isinstance(article['identifiers'], list):
                all_identifiers.extend(article['identifiers'])
        
        # 去重标识符
        unique_identifiers = []
        seen_identifiers = set()
        for identifier in all_identifiers:
            if isinstance(identifier, dict):
                key = f"{identifier.get('identifier_type')}:{identifier.get('identifier_value')}"
                if key not in seen_identifiers:
                    unique_identifiers.append(identifier)
                    seen_identifiers.add(key)
        
        merged_article['identifiers'] = unique_identifiers
        
        # 合并数据源信息
        sources = []
        for article in articles:
            if 'source_specific' in article and 'source' in article['source_specific']:
                source = article['source_specific']['source']
                if source not in sources:
                    sources.append(source)
        
        merged_article['merged_from_sources'] = sources
        merged_article['merge_count'] = len(articles)
        
        # 选择最佳字段值
        merged_article['article'] = self._merge_article_fields([a.get('article', {}) for a in articles])
        
        return merged_article
    
    def _select_most_complete_article(self, articles: List[Dict]) -> Dict:
        """选择最完整的文章作为合并基础
        
        Args:
            articles: 文章列表
            
        Returns:
            最完整的文章
        """
        def completeness_score(article):
            score = 0
            article_data = article.get('article', {})
            
            # 基础信息权重
            if article_data.get('title'): score += 10
            if article_data.get('abstract'): score += 8
            if article_data.get('publication_date'): score += 5
            
            # 作者信息权重
            authors = article.get('authors', [])
            score += min(len(authors) * 2, 10)
            
            # 标识符权重
            identifiers = article.get('identifiers', [])
            score += min(len(identifiers) * 3, 15)
            
            # 引用信息权重
            if article_data.get('citation_count'): score += 3
            if article_data.get('reference_count'): score += 2
            
            return score
        
        return max(articles, key=completeness_score)
    
    def _merge_article_fields(self, article_fields: List[Dict]) -> Dict:
        """合并文章字段信息
        
        Args:
            article_fields: 文章字段列表
            
        Returns:
            合并后的字段
        """
        merged = {}
        
        for field_dict in article_fields:
            for key, value in field_dict.items():
                if key not in merged or not merged[key]:
                    merged[key] = value
                elif key in ['citation_count', 'reference_count'] and isinstance(value, (int, float)):
                    # 对于数值字段，取最大值
                    if isinstance(merged[key], (int, float)):
                        merged[key] = max(merged[key], value)
        
        return merged
    
    def get_stats(self) -> Dict[str, int]:
        """获取去重统计信息
        
        Returns:
            统计信息字典
        """
        return self.stats.copy()


if __name__ == "__main__":
    # 测试去重功能
    test_articles = [
        {
            'article': {'title': 'Test Article 1', 'abstract': 'This is a test'},
            'identifiers': [{'identifier_type': 'doi', 'identifier_value': '10.1000/test1'}],
            'authors': [{'full_name': 'John Doe'}]
        },
        {
            'article': {'title': 'Test Article 1', 'abstract': 'This is a test article'},
            'identifiers': [{'identifier_type': 'doi', 'identifier_value': '10.1000/test1'}],
            'authors': [{'full_name': 'John Doe'}]
        },
        {
            'article': {'title': 'Different Article', 'abstract': 'This is different'},
            'identifiers': [{'identifier_type': 'doi', 'identifier_value': '10.1000/test2'}],
            'authors': [{'full_name': 'Jane Smith'}]
        }
    ]
    
    deduplicator = Deduplicator()
    unique_articles = deduplicator.deduplicate(test_articles)
    
    print(f"Original articles: {len(test_articles)}")
    print(f"Unique articles: {len(unique_articles)}")
    print(f"Stats: {deduplicator.get_stats()}")