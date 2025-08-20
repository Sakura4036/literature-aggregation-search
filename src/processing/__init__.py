"""
数据处理模块

包含文献去重、数据合并、数据验证等功能
"""

from .deduplicator import Deduplicator
from .merger import DataMerger
from .validator import DataValidator

__all__ = ['Deduplicator', 'DataMerger', 'DataValidator']