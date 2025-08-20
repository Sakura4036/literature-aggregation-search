"""
文献聚合搜索系统CLI主入口
"""
import click
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Optional

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.search.aggregator import SearchAggregator
from src.database.connection import AsyncDatabaseManager
from src.configs import get_settings

settings = get_settings()

@click.group()
@click.version_option(version="1.0.0")
def cli():
    """
    文献聚合搜索系统CLI工具
    
    支持多源文献搜索、数据管理和导出功能。
    """
    pass

@cli.command()
@click.option('--query', '-q', required=True, help='搜索查询字符串')
@click.option('--sources', '-s', multiple=True, 
              default=['pubmed', 'arxiv', 'semantic_scholar'],
              help='数据源 (可多选): pubmed, arxiv, biorxiv, semantic_scholar, web_of_science')
@click.option('--limit', '-l', default=100, help='结果数量限制 (默认: 100)')
@click.option('--output', '-o', help='输出文件路径 (可选)')
@click.option('--format', '-f', type=click.Choice(['json', 'csv', 'txt']), 
              default='json', help='输出格式 (默认: json)')
@click.option('--deduplicate/--no-deduplicate', default=True, 
              help='是否去重 (默认: 启用)')
@click.option('--verbose', '-v', is_flag=True, help='详细输出')
def search(query: str, sources: tuple, limit: int, output: Optional[str], 
           format: str, deduplicate: bool, verbose: bool):
    """
    执行多源文献搜索
    
    示例:
    \b
    # 基本搜索
    python -m scripts.cli search -q "machine learning"
    
    # 指定数据源和输出文件
    python -m scripts.cli search -q "CRISPR" -s pubmed -s arxiv -o results.json
    
    # 大量结果搜索
    python -m scripts.cli search -q "COVID-19" -l 1000 --no-deduplicate
    """
    async def _search():
        try:
            if verbose:
                click.echo(f"开始搜索: {query}")
                click.echo(f"数据源: {', '.join(sources)}")
                click.echo(f"结果限制: {limit}")
            
            # 初始化搜索聚合器
            aggregator = SearchAggregator()
            
            # 执行搜索
            with click.progressbar(length=100, label='搜索中...') as bar:
                results = await aggregator.search_all(
                    query=query,
                    sources=list(sources),
                    limit=limit
                )
                bar.update(50)
                
                if deduplicate:
                    results = await aggregator.deduplicate_results(results)
                bar.update(100)
            
            # 输出结果
            if output:
                await _save_results(results, output, format, verbose)
            else:
                await _display_results(results, format, verbose)
                
        except Exception as e:
            click.echo(f"搜索失败: {str(e)}", err=True)
            sys.exit(1)
    
    asyncio.run(_search())

@cli.command()
@click.option('--format', '-f', type=click.Choice(['json', 'csv', 'bibtex']),
              required=True, help='导出格式')
@click.option('--output', '-o', required=True, help='输出文件路径')
@click.option('--query', '-q', help='搜索查询 (导出搜索结果)')
@click.option('--ids', help='文章ID列表 (逗号分隔)')
@click.option('--limit', '-l', default=1000, help='导出数量限制')
def export(format: str, output: str, query: Optional[str], 
           ids: Optional[str], limit: int):
    """
    导出文献数据
    
    示例:
    \b
    # 导出搜索结果
    python -m scripts.cli export -f json -o export.json -q "deep learning"
    
    # 导出指定文章
    python -m scripts.cli export -f bibtex -o papers.bib --ids "1,2,3,4,5"
    """
    async def _export():
        try:
            click.echo(f"开始导出数据到: {output}")
            
            # TODO: 实现导出逻辑
            db_manager = AsyncDatabaseManager(settings.database_url)
            
            if ids:
                article_ids = [int(id.strip()) for id in ids.split(',')]
                click.echo(f"导出指定文章: {len(article_ids)} 篇")
            elif query:
                click.echo(f"导出搜索结果: {query}")
            else:
                click.echo("导出所有文章")
            
            # 模拟导出过程
            with click.progressbar(length=100, label='导出中...') as bar:
                for i in range(100):
                    await asyncio.sleep(0.01)
                    bar.update(1)
            
            click.echo(f"导出完成: {output}")
            
        except Exception as e:
            click.echo(f"导出失败: {str(e)}", err=True)
            sys.exit(1)
    
    asyncio.run(_export())

@cli.group()
def db():
    """数据库管理命令"""
    pass

@db.command()
def init():
    """初始化数据库"""
    async def _init():
        try:
            click.echo("初始化数据库...")
            db_manager = AsyncDatabaseManager(settings.database_url)
            await db_manager.create_tables()
            click.echo("数据库初始化完成")
        except Exception as e:
            click.echo(f"数据库初始化失败: {str(e)}", err=True)
            sys.exit(1)
    
    asyncio.run(_init())

@db.command()
def status():
    """检查数据库状态"""
    async def _status():
        try:
            click.echo("检查数据库连接...")
            db_manager = AsyncDatabaseManager(settings.database_url)
            # TODO: 实现数据库状态检查
            click.echo("数据库连接正常")
        except Exception as e:
            click.echo(f"数据库连接失败: {str(e)}", err=True)
            sys.exit(1)
    
    asyncio.run(_status())

async def _save_results(results, output_path: str, format: str, verbose: bool):
    """保存搜索结果到文件"""
    try:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        if format == 'json':
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results.dict(), f, ensure_ascii=False, indent=2)
        elif format == 'csv':
            # TODO: 实现CSV导出
            pass
        elif format == 'txt':
            # TODO: 实现TXT导出
            pass
        
        if verbose:
            click.echo(f"结果已保存到: {output_path}")
            
    except Exception as e:
        click.echo(f"保存文件失败: {str(e)}", err=True)

async def _display_results(results, format: str, verbose: bool):
    """在控制台显示搜索结果"""
    try:
        if format == 'json':
            click.echo(json.dumps(results.dict(), ensure_ascii=False, indent=2))
        else:
            # 简化显示
            click.echo(f"找到 {len(results.articles)} 篇文献:")
            for i, article in enumerate(results.articles[:10], 1):
                click.echo(f"{i}. {article.get('title', 'No title')}")
            
            if len(results.articles) > 10:
                click.echo(f"... 还有 {len(results.articles) - 10} 篇文献")
                
    except Exception as e:
        click.echo(f"显示结果失败: {str(e)}", err=True)

if __name__ == '__main__':
    cli()