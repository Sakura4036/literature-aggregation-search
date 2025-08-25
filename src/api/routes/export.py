import csv
import json
from io import StringIO
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.api.schemas import ExportRequest, ExportResponse, ExportFormat
from src.database.connection import get_db_session
from src.database.models import Article

router = APIRouter()

async def get_articles_by_ids(db: AsyncSession, article_ids: List[int]) -> List[Article]:
    """Fetch articles from the database by a list of IDs."""
    if not article_ids:
        return []
    result = await db.execute(select(Article).where(Article.id.in_(article_ids)))
    return result.scalars().all()

@router.post("/export", response_model=ExportResponse)
async def export_articles(
    request: ExportRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Export articles in a specified format (JSON or CSV).
    """
    articles = []
    if request.article_ids:
        articles = await get_articles_by_ids(db, request.article_ids)
    elif request.search_query:
        # This part is complex and depends on the search implementation.
        # For now, we will raise a 501 Not Implemented error.
        raise HTTPException(status_code=501, detail="Export by search query is not yet implemented.")
    else:
        raise HTTPException(status_code=400, detail="Either article_ids or search_query must be provided.")

    if not articles:
        raise HTTPException(status_code=404, detail="No articles found for the given IDs.")

    content, media_type, filename = await format_export_data(articles, request.format)

    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

async def format_export_data(articles: List[Article], export_format: ExportFormat):
    """Formats the article data into the specified export format."""
    if export_format == ExportFormat.JSON:
        data = [
            {
                "id": article.id,
                "title": article.title,
                "abstract": article.abstract,
                "publication_year": article.publication_year,
                "doi": article.primary_doi
            }
            for article in articles
        ]
        content = json.dumps(data, indent=2)
        media_type = "application/json"
        filename = "articles.json"
    elif export_format == ExportFormat.CSV:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "title", "abstract", "publication_year", "doi"])
        for article in articles:
            writer.writerow([
                article.id,
                article.title,
                article.abstract,
                article.publication_year,
                article.primary_doi
            ])
        content = output.getvalue()
        media_type = "text/csv"
        filename = "articles.csv"
    elif export_format == ExportFormat.BIBTEX:
        raise HTTPException(status_code=501, detail="BibTeX export is not yet implemented.")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported export format: {export_format}")

    return content, media_type, filename
