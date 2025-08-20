#!/usr/bin/env python3
"""
PubMed MeSH搜索使用示例

这个文件展示了如何使用pubmed_mesh_search.py脚本进行各种搜索
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from pubmed_mesh_search import PubMedMeshSearcher


def example_basic_search():
    """基本搜索示例"""
    print("=== 基本搜索示例 ===")
    
    # 创建搜索器
    searcher = PubMedMeshSearcher(email="your.email@example.com")
    
    # 搜索人工智能相关文献（最近5年）
    articles = searcher.search_mesh_term_by_years(
        mesh_term="Artificial Intelligence",
        start_year=2020,
        end_year=2024
    )
    
    # 保存结果
    searcher.save_results(articles, "ai_recent_articles.json")


def example_long_term_search():
    """长期搜索示例"""
    print("=== 长期搜索示例 ===")
    
    searcher = PubMedMeshSearcher(email="your.email@example.com")
    
    # 搜索机器学习相关文献（从1990年开始）
    articles = searcher.search_mesh_term_by_years(
        mesh_term="Machine Learning",
        start_year=1990,
        end_year=2024
    )
    
    searcher.save_results(articles, "ml_historical_articles.json")


def example_medical_search():
    """医学主题搜索示例"""
    print("=== 医学主题搜索示例 ===")
    
    searcher = PubMedMeshSearcher(email="your.email@example.com")
    
    # 搜索癌症治疗相关文献
    articles = searcher.search_mesh_term_by_years(
        mesh_term="Neoplasms/therapy",
        start_year=2015,
        end_year=2024
    )
    
    searcher.save_results(articles, "cancer_therapy_articles.json")


if __name__ == "__main__":
    # 运行示例（取消注释想要运行的示例）
    
    # example_basic_search()
    # example_long_term_search()
    # example_medical_search()
    
    print("请取消注释想要运行的示例函数")