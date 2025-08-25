#!/usr/bin/env python3
"""
文献聚合搜索系统主入口

提供命令行接口和基本的搜索功能演示
"""

import sys
import os
import argparse
import json
from typing import Optional, List

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.search.aggregator import search_literature


def progress_callback(progress):
    """进度回调函数"""
    print(f"\rProgress: {progress['progress_percentage']:.1f}% - "
          f"{progress['completed_sources']}/{progress['total_sources']} sources - "
          f"{progress['results_count']} results", end='', flush=True)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='文献聚合搜索系统 - 跨多个学术数据库搜索文献',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python main.py "synthetic biology" --sources pubmed arxiv --num-results 20
  python main.py "machine learning" --output results.json --deduplicate
  python main.py "covid-19" --sources pubmed semantic_scholar --year 2020-2023
        """
    )
    
    # 必需参数
    parser.add_argument('query', help='搜索查询字符串')
    
    # 可选参数
    parser.add_argument('--sources', nargs='+', 
                       choices=['pubmed', 'arxiv', 'biorxiv', 'semantic_scholar'],
                       help='指定要搜索的数据源 (默认: 所有)')
    
    parser.add_argument('--num-results', type=int, default=50,
                       help='返回结果数量 (默认: 50, 最大: 10000)')
    
    parser.add_argument('--year', help='年份范围，格式: YYYY 或 YYYY-YYYY')
    
    parser.add_argument('--output', '-o', help='输出文件路径 (JSON格式)')
    
    parser.add_argument('--deduplicate', action='store_true',
                       help='启用智能去重 (默认: 启用)')
    
    parser.add_argument('--no-deduplicate', action='store_true',
                       help='禁用去重')
    
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='显示详细信息')
    
    parser.add_argument('--test', action='store_true',
                       help='运行功能测试')
    
    args = parser.parse_args()
    
    # 运行测试
    if args.test:
        print("运行功能测试...")
        try:
            import test_aggregator
            test_aggregator.main()
        except ImportError:
            print("错误: 找不到测试模块")
            return 1
        return 0
    
    # 验证参数
    if args.num_results <= 0 or args.num_results > 10000:
        print("错误: 结果数量必须在1-10000之间")
        return 1
    
    # 确定是否去重
    deduplicate = True
    if args.no_deduplicate:
        deduplicate = False
    elif args.deduplicate:
        deduplicate = True
    
    print(f"搜索查询: {args.query}")
    if args.sources:
        print(f"数据源: {', '.join(args.sources)}")
    else:
        print("数据源: 所有可用数据源")
    print(f"结果数量: {args.num_results}")
    print(f"去重: {'启用' if deduplicate else '禁用'}")
    if args.year:
        print(f"年份范围: {args.year}")
    print("-" * 50)
    
    try:
        # 构建搜索参数
        search_params = {
            'query': args.query,
            'sources': args.sources,
            'num_results': args.num_results,
            'deduplicate': deduplicate,
            'progress_callback': progress_callback if not args.verbose else None
        }
        
        # 添加年份参数
        if args.year:
            search_params['year'] = args.year
        
        # 执行搜索
        print("开始搜索...")
        results = search_literature(**search_params)
        print()  # 换行
        
        # 显示结果摘要
        metadata = results['metadata']
        print(f"\n搜索完成!")
        print(f"总结果数: {metadata['total_results']}")
        print(f"搜索的数据源: {', '.join(metadata['sources_searched'])}")
        print(f"搜索时间: {metadata['search_time']:.2f}秒")
        
        if metadata.get('duplicates_removed', 0) > 0:
            print(f"移除的重复项: {metadata['duplicates_removed']}")
        
        if metadata.get('errors'):
            print(f"错误: {len(metadata['errors'])}")
            if args.verbose:
                for error in metadata['errors']:
                    print(f"  - {error}")
        
        # 显示结果预览
        if results['results']:
            print(f"\n前5个结果:")
            for i, article in enumerate(results['results'][:5]):
                title = article.get('article', {}).get('title', 'No title')
                source = article.get('source_specific', {}).get('source', 'Unknown')
                year = article.get('article', {}).get('publication_year', 'Unknown')
                print(f"{i+1}. [{source}] ({year}) {title[:80]}...")
        
        # 保存结果
        if args.output:
            print(f"\n保存结果到: {args.output}")
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print("保存完成!")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n搜索被用户中断")
        return 1
    except Exception as e:
        print(f"\n搜索过程中发生错误: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
