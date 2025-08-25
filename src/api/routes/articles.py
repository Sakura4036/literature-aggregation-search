from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from ...database.connection import get_db_session
from ...database.models import Article
from ..schemas import Article as ArticleSchema

router = APIRouter()

@router.get("/articles", response_model=List[ArticleSchema])
async def get_articles(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get a list of articles with pagination.
    """
    result = await db.execute(select(Article).offset(skip).limit(limit))
    articles = result.scalars().all()
    return articles

@router.get("/articles/{article_id}", response_model=ArticleSchema)
async def get_article(article_id: int, db: AsyncSession = Depends(get_db_session)):
    """
    Get a single article by its ID.
    """
    result = await db.execute(select(Article).filter(Article.id == article_id))
    article = result.scalars().first()
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article
