"""
数据验证器 - 验证文献数据的完整性和质量

实现数据质量检查、格式验证、完整性评估等功能
"""

import logging
import re
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class ValidationResult:
    """验证结果类"""
    
    def __init__(self):
        self.is_valid = True
        self.errors = []
        self.warnings = []
        self.quality_score = 0.0
        self.completeness_score = 0.0
    
    def add_error(self, message: str, field: str = None):
        """添加错误"""
        self.is_valid = False
        error = {'message': message, 'field': field, 'type': 'error'}
        self.errors.append(error)
        logger.error(f"Validation error: {message} (field: {field})")
    
    def add_warning(self, message: str, field: str = None):
        """添加警告"""
        warning = {'message': message, 'field': field, 'type': 'warning'}
        self.warnings.append(warning)
        logger.warning(f"Validation warning: {message} (field: {field})")
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'is_valid': self.is_valid,
            'errors': self.errors,
            'warnings': self.warnings,
            'quality_score': self.quality_score,
            'completeness_score': self.completeness_score
        }


class DataValidator:
    """数据验证器"""
    
    # DOI格式正则表达式
    DOI_PATTERN = re.compile(r'^10\.\d{4,}/[^\s]+$')
    
    # PMID格式正则表达式（纯数字）
    PMID_PATTERN = re.compile(r'^\d+$')
    
    # ArXiv ID格式正则表达式
    ARXIV_PATTERN = re.compile(r'^(\d{4}\.\d{4,5}|[a-z-]+(\.[A-Z]{2})?/\d{7})(v\d+)?$')
    
    # 必需字段
    REQUIRED_FIELDS = {
        'article': ['title'],
        'identifiers': [],  # 至少需要一个标识符
    }
    
    # 字段长度限制
    FIELD_LENGTH_LIMITS = {
        'title': (10, 500),      # 标题长度范围
        'abstract': (50, 5000),  # 摘要长度范围
        'doi': (10, 100),        # DOI长度范围
        'pmid': (1, 20),         # PMID长度范围
    }
    
    def __init__(self):
        """初始化验证器"""
        self.validation_stats = {
            'total_validated': 0,
            'valid_articles': 0,
            'invalid_articles': 0,
            'warnings_count': 0,
            'errors_count': 0
        }
    
    def validate_article(self, article: Dict) -> ValidationResult:
        """验证单篇文章
        
        Args:
            article: 文章数据
            
        Returns:
            验证结果
        """
        result = ValidationResult()
        
        # 基本结构验证
        self._validate_structure(article, result)
        
        # 字段内容验证
        self._validate_article_fields(article.get('article', {}), result)
        self._validate_authors(article.get('authors', []), result)
        self._validate_identifiers(article.get('identifiers', []), result)
        self._validate_venue(article.get('venue', {}), result)
        
        # 计算质量分数
        result.quality_score = self._calculate_quality_score(article)
        result.completeness_score = self._calculate_completeness_score(article)
        
        # 更新统计
        self.validation_stats['total_validated'] += 1
        if result.is_valid:
            self.validation_stats['valid_articles'] += 1
        else:
            self.validation_stats['invalid_articles'] += 1
        
        self.validation_stats['errors_count'] += len(result.errors)
        self.validation_stats['warnings_count'] += len(result.warnings)
        
        return result
    
    def validate_batch(self, articles: List[Dict]) -> List[ValidationResult]:
        """批量验证文章
        
        Args:
            articles: 文章列表
            
        Returns:
            验证结果列表
        """
        results = []
        
        for i, article in enumerate(articles):
            try:
                result = self.validate_article(article)
                results.append(result)
            except Exception as e:
                error_result = ValidationResult()
                error_result.add_error(f"Validation failed: {str(e)}", f"article_{i}")
                results.append(error_result)
        
        return results
    
    def _validate_structure(self, article: Dict, result: ValidationResult):
        """验证文章基本结构
        
        Args:
            article: 文章数据
            result: 验证结果
        """
        if not isinstance(article, dict):
            result.add_error("Article must be a dictionary")
            return
        
        # 检查必需的顶级字段
        required_sections = ['article']
        for section in required_sections:
            if section not in article:
                result.add_error(f"Missing required section: {section}")
            elif not isinstance(article[section], dict):
                result.add_error(f"Section '{section}' must be a dictionary")
        
        # 检查可选字段的类型
        optional_sections = {
            'authors': list,
            'identifiers': list,
            'venue': dict,
            'publication_types': list,
            'source_specific': dict
        }
        
        for section, expected_type in optional_sections.items():
            if section in article and not isinstance(article[section], expected_type):
                result.add_error(f"Section '{section}' must be a {expected_type.__name__}")
    
    def _validate_article_fields(self, article_data: Dict, result: ValidationResult):
        """验证文章字段内容
        
        Args:
            article_data: 文章数据
            result: 验证结果
        """
        # 验证标题
        title = article_data.get('title', '').strip()
        if not title:
            result.add_error("Title is required", 'title')
        else:
            min_len, max_len = self.FIELD_LENGTH_LIMITS['title']
            if len(title) < min_len:
                result.add_warning(f"Title is too short (minimum {min_len} characters)", 'title')
            elif len(title) > max_len:
                result.add_warning(f"Title is too long (maximum {max_len} characters)", 'title')
        
        # 验证摘要
        abstract = article_data.get('abstract', '').strip()
        if abstract:
            min_len, max_len = self.FIELD_LENGTH_LIMITS['abstract']
            if len(abstract) < min_len:
                result.add_warning(f"Abstract is too short (minimum {min_len} characters)", 'abstract')
            elif len(abstract) > max_len:
                result.add_warning(f"Abstract is too long (maximum {max_len} characters)", 'abstract')
        else:
            result.add_warning("Abstract is missing", 'abstract')
        
        # 验证发表年份
        pub_year = article_data.get('publication_year')
        if pub_year:
            if not isinstance(pub_year, int):
                result.add_error("Publication year must be an integer", 'publication_year')
            elif pub_year < 1900 or pub_year > datetime.now().year + 1:
                result.add_error(f"Invalid publication year: {pub_year}", 'publication_year')
        
        # 验证发表日期
        pub_date = article_data.get('publication_date')
        if pub_date:
            if not self._is_valid_date_string(pub_date):
                result.add_error(f"Invalid publication date format: {pub_date}", 'publication_date')
        
        # 验证引用数
        citation_count = article_data.get('citation_count')
        if citation_count is not None:
            if not isinstance(citation_count, (int, float)) or citation_count < 0:
                result.add_error("Citation count must be a non-negative number", 'citation_count')
        
        # 验证参考文献数
        ref_count = article_data.get('reference_count')
        if ref_count is not None:
            if not isinstance(ref_count, (int, float)) or ref_count < 0:
                result.add_error("Reference count must be a non-negative number", 'reference_count')
    
    def _validate_authors(self, authors: List, result: ValidationResult):
        """验证作者信息
        
        Args:
            authors: 作者列表
            result: 验证结果
        """
        if not authors:
            result.add_warning("No authors specified", 'authors')
            return
        
        if not isinstance(authors, list):
            result.add_error("Authors must be a list", 'authors')
            return
        
        for i, author in enumerate(authors):
            if isinstance(author, dict):
                full_name = author.get('full_name', '').strip()
                if not full_name:
                    result.add_warning(f"Author {i+1} missing full name", f'authors[{i}].full_name')
                elif len(full_name) < 2:
                    result.add_warning(f"Author {i+1} name too short", f'authors[{i}].full_name')
            elif isinstance(author, str):
                if not author.strip():
                    result.add_warning(f"Author {i+1} name is empty", f'authors[{i}]')
            else:
                result.add_error(f"Author {i+1} must be a string or dictionary", f'authors[{i}]')
    
    def _validate_identifiers(self, identifiers: List, result: ValidationResult):
        """验证标识符
        
        Args:
            identifiers: 标识符列表
            result: 验证结果
        """
        if not identifiers:
            result.add_warning("No identifiers specified", 'identifiers')
            return
        
        if not isinstance(identifiers, list):
            result.add_error("Identifiers must be a list", 'identifiers')
            return
        
        valid_identifier_types = {'doi', 'pmid', 'arxiv_id', 'semantic_scholar_id', 'wos_uid', 'pii', 'pmc_id'}
        seen_types = set()
        
        for i, identifier in enumerate(identifiers):
            if not isinstance(identifier, dict):
                result.add_error(f"Identifier {i+1} must be a dictionary", f'identifiers[{i}]')
                continue
            
            id_type = identifier.get('identifier_type')
            id_value = identifier.get('identifier_value')
            
            if not id_type:
                result.add_error(f"Identifier {i+1} missing type", f'identifiers[{i}].identifier_type')
                continue
            
            if not id_value:
                result.add_error(f"Identifier {i+1} missing value", f'identifiers[{i}].identifier_value')
                continue
            
            # 检查标识符类型是否有效
            if id_type not in valid_identifier_types:
                result.add_warning(f"Unknown identifier type: {id_type}", f'identifiers[{i}].identifier_type')
            
            # 检查重复的标识符类型
            if id_type in seen_types:
                result.add_warning(f"Duplicate identifier type: {id_type}", f'identifiers[{i}].identifier_type')
            seen_types.add(id_type)
            
            # 验证标识符格式
            self._validate_identifier_format(id_type, str(id_value), result, f'identifiers[{i}].identifier_value')
    
    def _validate_identifier_format(self, id_type: str, id_value: str, result: ValidationResult, field_path: str):
        """验证标识符格式
        
        Args:
            id_type: 标识符类型
            id_value: 标识符值
            result: 验证结果
            field_path: 字段路径
        """
        id_value = id_value.strip()
        
        if id_type == 'doi':
            if not self.DOI_PATTERN.match(id_value):
                result.add_error(f"Invalid DOI format: {id_value}", field_path)
        
        elif id_type == 'pmid':
            if not self.PMID_PATTERN.match(id_value):
                result.add_error(f"Invalid PMID format: {id_value}", field_path)
        
        elif id_type == 'arxiv_id':
            if not self.ARXIV_PATTERN.match(id_value):
                result.add_error(f"Invalid ArXiv ID format: {id_value}", field_path)
        
        # 检查长度限制
        if id_type in self.FIELD_LENGTH_LIMITS:
            min_len, max_len = self.FIELD_LENGTH_LIMITS[id_type]
            if len(id_value) < min_len or len(id_value) > max_len:
                result.add_error(f"Invalid {id_type} length: {len(id_value)} (expected {min_len}-{max_len})", field_path)
    
    def _validate_venue(self, venue: Dict, result: ValidationResult):
        """验证期刊/会议信息
        
        Args:
            venue: 期刊信息
            result: 验证结果
        """
        if not venue:
            result.add_warning("No venue information", 'venue')
            return
        
        venue_name = venue.get('venue_name', '').strip()
        if not venue_name:
            result.add_warning("Venue name is missing", 'venue.venue_name')
        elif len(venue_name) < 3:
            result.add_warning("Venue name is too short", 'venue.venue_name')
        
        venue_type = venue.get('venue_type')
        if venue_type:
            valid_types = {'journal', 'conference', 'preprint_server', 'book', 'other'}
            if venue_type not in valid_types:
                result.add_warning(f"Unknown venue type: {venue_type}", 'venue.venue_type')
    
    def _is_valid_date_string(self, date_str: str) -> bool:
        """检查日期字符串格式是否有效
        
        Args:
            date_str: 日期字符串
            
        Returns:
            是否有效
        """
        date_formats = ['%Y-%m-%d', '%Y-%m', '%Y']
        
        for fmt in date_formats:
            try:
                datetime.strptime(date_str, fmt)
                return True
            except ValueError:
                continue
        
        return False
    
    def _calculate_quality_score(self, article: Dict) -> float:
        """计算文章质量分数
        
        Args:
            article: 文章数据
            
        Returns:
            质量分数 (0-100)
        """
        score = 0.0
        max_score = 100.0
        
        article_data = article.get('article', {})
        
        # 标题质量 (20分)
        title = article_data.get('title', '').strip()
        if title:
            if len(title) >= 20:
                score += 20
            else:
                score += len(title)  # 部分分数
        
        # 摘要质量 (25分)
        abstract = article_data.get('abstract', '').strip()
        if abstract:
            if len(abstract) >= 100:
                score += 25
            else:
                score += min(25, len(abstract) / 4)  # 部分分数
        
        # 作者信息 (15分)
        authors = article.get('authors', [])
        if authors:
            score += min(15, len(authors) * 3)
        
        # 标识符 (20分)
        identifiers = article.get('identifiers', [])
        if identifiers:
            score += min(20, len(identifiers) * 5)
        
        # 发表信息 (10分)
        if article_data.get('publication_date') or article_data.get('publication_year'):
            score += 10
        
        # 期刊信息 (10分)
        venue = article.get('venue', {})
        if venue.get('venue_name'):
            score += 10
        
        return min(score, max_score)
    
    def _calculate_completeness_score(self, article: Dict) -> float:
        """计算文章完整性分数
        
        Args:
            article: 文章数据
            
        Returns:
            完整性分数 (0-100)
        """
        total_fields = 0
        present_fields = 0
        
        # 检查核心字段
        core_fields = [
            ('article.title', article.get('article', {}).get('title')),
            ('article.abstract', article.get('article', {}).get('abstract')),
            ('article.publication_date', article.get('article', {}).get('publication_date')),
            ('authors', article.get('authors')),
            ('identifiers', article.get('identifiers')),
            ('venue.venue_name', article.get('venue', {}).get('venue_name')),
        ]
        
        for field_name, field_value in core_fields:
            total_fields += 1
            if field_value:
                if isinstance(field_value, (list, dict)):
                    if len(field_value) > 0:
                        present_fields += 1
                elif str(field_value).strip():
                    present_fields += 1
        
        # 检查可选字段
        optional_fields = [
            ('article.citation_count', article.get('article', {}).get('citation_count')),
            ('article.reference_count', article.get('article', {}).get('reference_count')),
            ('article.is_open_access', article.get('article', {}).get('is_open_access')),
            ('publication_types', article.get('publication_types')),
        ]
        
        for field_name, field_value in optional_fields:
            total_fields += 1
            if field_value is not None:
                if isinstance(field_value, (list, dict)):
                    if len(field_value) > 0:
                        present_fields += 1
                else:
                    present_fields += 1
        
        return (present_fields / total_fields * 100) if total_fields > 0 else 0.0
    
    def get_validation_stats(self) -> Dict[str, int]:
        """获取验证统计信息
        
        Returns:
            统计信息字典
        """
        return self.validation_stats.copy()
    
    def reset_stats(self):
        """重置统计信息"""
        self.validation_stats = {
            'total_validated': 0,
            'valid_articles': 0,
            'invalid_articles': 0,
            'warnings_count': 0,
            'errors_count': 0
        }


if __name__ == "__main__":
    # 测试数据验证功能
    test_article = {
        'article': {
            'title': 'Test Article Title',
            'abstract': 'This is a test abstract with sufficient length to pass validation checks.',
            'publication_year': 2023,
            'publication_date': '2023-01-15',
            'citation_count': 10
        },
        'authors': [
            {'full_name': 'John Doe'},
            {'full_name': 'Jane Smith'}
        ],
        'identifiers': [
            {'identifier_type': 'doi', 'identifier_value': '10.1000/test123'},
            {'identifier_type': 'pmid', 'identifier_value': '12345678'}
        ],
        'venue': {
            'venue_name': 'Test Journal',
            'venue_type': 'journal'
        }
    }
    
    validator = DataValidator()
    result = validator.validate_article(test_article)
    
    print("Validation Result:")
    print(f"Valid: {result.is_valid}")
    print(f"Quality Score: {result.quality_score:.1f}")
    print(f"Completeness Score: {result.completeness_score:.1f}")
    print(f"Errors: {len(result.errors)}")
    print(f"Warnings: {len(result.warnings)}")
    
    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f"  - {error['message']} (field: {error['field']})")
    
    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  - {warning['message']} (field: {warning['field']})")
    
    print(f"\nStats: {validator.get_validation_stats()}")