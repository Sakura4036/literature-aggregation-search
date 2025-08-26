"""
文献聚合搜索系统CLI主入口
"""
import click
import asyncio
import json
import csv
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.search.aggregator import SearchAggregator
from src.configs import get_settings
from src.models.schemas import LiteratureSchema

settings = get_settings()

# --- Utility Functions ---

def _flatten_article(article_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Flattens a nested article dictionary for CSV export. Returns None if data is malformed."""
    if not isinstance(article_data, dict):
        click.echo(f"Warning: Skipping malformed search result item: {type(article_data)}", err=True)
        return None

    try:
        # Use LiteratureSchema to structure and default the data
        schema = LiteratureSchema.from_dict(article_data)

        # Flatten authors
        authors_list = [f"{author.full_name} ({author.affiliation or 'N/A'})" for author in schema.authors]

        return {
            "title": schema.article.title,
            "authors": "; ".join(authors_list),
            "publication_year": schema.article.publication_year,
            "venue": schema.venue.venue_name,
            "doi": schema.get_doi(),
            "pmid": schema.get_pmid(),
            "arxiv_id": schema.get_arxiv_id(),
            "abstract": schema.article.abstract,
            "citation_count": schema.article.citation_count,
            "source": article_data.get('source_specific', {}).get('source', 'N/A'),
        }
    except Exception as e:
        click.echo(f"Warning: Could not process article. Error: {e}. Skipping.", err=True)
        return None

async def _save_as_json(results: Dict[str, Any], output_path: str):
    """Saves search results as a JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

async def _save_as_csv(results: Dict[str, Any], output_path: str):
    """Saves search results as a CSV file."""
    articles = results.get('results', [])
    if not articles:
        click.echo("No articles to save.")
        return

    # Flatten and filter out malformed articles
    flat_articles = [_flatten_article(article) for article in articles]
    valid_articles = [article for article in flat_articles if article is not None]

    if not valid_articles:
        click.echo("No valid data to write to CSV.")
        return

    fieldnames = list(valid_articles[0].keys())

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(valid_articles)

async def _save_as_txt(results: Dict[str, Any], output_path: str):
    """Saves search results as a human-readable text file."""
    articles = results.get('results', [])
    valid_articles = [article for article in articles if isinstance(article, dict)]

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"Found {len(valid_articles)} valid articles.\n")
        f.write("=" * 20 + "\n\n")
        for i, article_data in enumerate(valid_articles, 1):
            try:
                schema = LiteratureSchema.from_dict(article_data)
                f.write(f"#{i}: {schema.article.title}\n")
                f.write(f"  Authors: {'; '.join([a.full_name for a in schema.authors])}\n")
                f.write(f"  Venue: {schema.venue.venue_name} ({schema.article.publication_year})\n")
                f.write(f"  DOI: {schema.get_doi() or 'N/A'}\n")
                f.write(f"  Abstract: {schema.article.abstract or 'N/A'}\n\n")
            except Exception as e:
                click.echo(f"Warning: Could not process article for TXT output. Error: {e}. Skipping.", err=True)


async def _save_results(results: Dict[str, Any], output_path: str, format: str, verbose: bool):
    """Dispatches saving results to the correct format handler."""
    try:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if format == 'json':
            await _save_as_json(results, output_path)
        elif format == 'csv':
            await _save_as_csv(results, output_path)
        elif format == 'txt':
            await _save_as_txt(results, output_path)

        if verbose:
            click.echo(f"Results saved to: {output_path}")

    except Exception as e:
        click.echo(f"Failed to save file: {str(e)}", err=True)

def _display_as_json(results: Dict[str, Any]):
    """Displays search results as JSON in the console."""
    click.echo(json.dumps(results, ensure_ascii=False, indent=2))

def _display_as_summary(results: Dict[str, Any]):
    """Displays a summary of search results in the console."""
    articles = results.get('results', [])
    valid_articles = [article for article in articles if isinstance(article, dict)]

    click.echo(f"Found {len(valid_articles)} valid articles:")
    for i, article_data in enumerate(valid_articles[:10], 1):
        try:
            schema = LiteratureSchema.from_dict(article_data)
            click.echo(f"{i}. {schema.article.title} ({schema.article.publication_year})")
            click.echo(f"   DOI: {schema.get_doi() or 'N/A'}")
        except Exception as e:
             click.echo(f"Warning: Could not display article. Error: {e}. Skipping.", err=True)

    if len(valid_articles) > 10:
        click.echo(f"... and {len(valid_articles) - 10} more.")

async def _display_results(results: Dict[str, Any], format: str, verbose: bool):
    """Dispatches displaying results to the correct format handler."""
    try:
        if format == 'json':
            _display_as_json(results)
        else:
            _display_as_summary(results)
    except Exception as e:
        click.echo(f"Failed to display results: {str(e)}", err=True)

# --- CLI Commands ---

@click.group()
@click.version_option(version="1.0.0")
def cli():
    """
    Literature Aggregation Search System CLI Tool.
    Supports multi-source literature search, data management, and export functions.
    """
    pass

@cli.command()
@click.option('--query', '-q', required=True, help='Search query string.')
@click.option('--sources', '-s', multiple=True, 
              default=['pubmed', 'arxiv', 'semantic_scholar'],
              type=click.Choice(['pubmed', 'arxiv', 'biorxiv', 'semantic_scholar', 'wos']),
              help='Data source (multiple allowed).')
@click.option('--limit', '-l', default=20, help='Limit on the number of results (default: 20).')
@click.option('--output', '-o', help='Output file path (optional).')
@click.option('--format', '-f', type=click.Choice(['json', 'csv', 'txt']), 
              default='json', help='Output format (default: json).')
@click.option('--deduplicate/--no-deduplicate', default=True, 
              help='Enable/disable deduplication (default: enabled).')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output.')
def search(query: str, sources: tuple, limit: int, output: Optional[str], 
           format: str, deduplicate: bool, verbose: bool):
    """
    Perform a multi-source literature search.
    
    Examples:
    \b
    # Basic search
    python -m scripts.cli search -q "machine learning"
    
    # Specify sources and output file
    python -m scripts.cli search -q "CRISPR" -s pubmed -s arxiv -o results.json
    
    # Search for a large number of results without deduplication
    python -m scripts.cli search -q "COVID-19" -l 100 --no-deduplicate
    """
    async def _search():
        try:
            if verbose:
                click.echo(f"Starting search for: '{query}'")
                click.echo(f"Sources: {', '.join(sources)}")
                click.echo(f"Result limit: {limit}")
            
            aggregator = SearchAggregator()
            
            with click.progressbar(length=100, label='Searching...') as bar:
                def progress_callback(p):
                    # Ensure progress doesn't exceed 100
                    progress_value = min(100, int(p.get('progress_percentage', 0)))
                    # Only update if progress has increased
                    if progress_value > bar.pos:
                        bar.update(progress_value - bar.pos)

                results = await asyncio.to_thread(
                    aggregator.search_with_deduplication,
                    query=query,
                    sources=list(sources),
                    deduplicate=deduplicate,
                    num_results=limit,
                    progress_callback=progress_callback if verbose else None
                )
                # Ensure the bar is full on completion
                if bar.pos < 100:
                    bar.update(100 - bar.pos)

            if verbose:
                meta = results.get('metadata', {})
                click.echo(f"Search complete. Found {meta.get('total_results', 0)} unique articles.")
                if meta.get('errors'):
                    click.echo("Errors occurred:", err=True)
                    for error in meta['errors']:
                        click.echo(f"- {error}", err=True)

            if output:
                await _save_results(results, output, format, verbose)
            else:
                await _display_results(results, format, verbose)
                
        except Exception as e:
            click.echo(f"Search failed: {str(e)}", err=True)
            sys.exit(1)
    
    asyncio.run(_search())

@cli.command()
@click.option('--format', '-f', type=click.Choice(['json', 'csv', 'bibtex']),
              required=True, help='Export format.')
@click.option('--output', '-o', required=True, help='Output file path.')
@click.option('--query', '-q', help='Search query to export results for.')
@click.option('--ids', help='List of article IDs (comma-separated, not yet supported).')
@click.option('--limit', '-l', default=100, help='Limit for the number of articles to export.')
def export(format: str, output: str, query: Optional[str], 
           ids: Optional[str], limit: int):
    """
    Export literature data.
    
    Examples:
    \b
    # Export search results to CSV
    python -m scripts.cli export -f csv -o export.csv -q "deep learning"
    
    # Export specific articles by ID (not yet functional)
    python -m scripts.cli export -f bibtex -o papers.bib --ids "1,2,3"
    """
    async def _export():
        if ids:
            click.echo("Exporting by ID is not yet supported as it requires a populated database.", err=True)
            sys.exit(1)
            
        if format == 'bibtex':
            click.echo("BibTeX export format is not yet implemented.", err=True)
            sys.exit(1)

        if not query:
            click.echo("A search query (-q) is required for exporting.", err=True)
            sys.exit(1)
            
        try:
            click.echo(f"Starting export for query: '{query}'")
            aggregator = SearchAggregator()
            
            with click.progressbar(length=100, label='Searching and exporting...') as bar:
                results = await asyncio.to_thread(
                    aggregator.search_with_deduplication,
                    query=query,
                    deduplicate=True,
                    num_results=limit
                )
                bar.update(100)

            await _save_results(results, output, format, verbose=True)
            
        except Exception as e:
            click.echo(f"Export failed: {str(e)}", err=True)
            sys.exit(1)
    
    asyncio.run(_export())

@cli.group()
def db():
    """Database management commands."""
    pass

@db.command()
def init():
    """Initialize the database."""
    async def _init():
        from src.database.connection import AsyncDatabaseManager
        try:
            click.echo("Initializing database...")
            db_manager = AsyncDatabaseManager(settings.database_url)
            # This will fail because models are not defined. We catch this to give a nice error.
            await db_manager.create_tables()
            click.echo("Database initialized successfully.")
        except Exception as e:
            click.echo("Failed to initialize database.", err=True)
            click.echo("Error: The database models are not yet defined in the code.", err=True)
            click.echo(f"Details: {e}", err=True)
            sys.exit(1)
    
    asyncio.run(_init())

@db.command()
def status():
    """Check the database connection status."""
    async def _status():
        from src.database.connection import AsyncDatabaseManager
        try:
            click.echo("Checking database connection...")
            db_manager = AsyncDatabaseManager(settings.database_url)
            is_healthy = await db_manager.health_check()
            if is_healthy:
                click.echo("Database connection is healthy.")
            else:
                click.echo("Database connection failed.", err=True)
                sys.exit(1)
        except Exception as e:
            click.echo(f"Database connection failed: {str(e)}", err=True)
            sys.exit(1)
    
    asyncio.run(_status())

if __name__ == '__main__':
    cli()