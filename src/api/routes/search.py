"""
搜索相关API路由
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List, Optional
import asyncio
import time

from ..schemas import SearchRequest, SearchResponse, SearchMetadata, ArticleDetail
from ...search.aggregator import SearchAggregator
from ...database.connection import get_db_session
from ..dependencies import get_search_aggregator

router = APIRouter()

@router.post("/search", response_model=SearchResponse)
async def multi_source_search(
    request: SearchRequest,
    aggregator: SearchAggregator = Depends(get_search_aggregator),
    db_session = Depends(get_db_session)
):
    """
    多源聚合搜索
    
    执行跨多个学术数据库的聚合搜索，支持去重和结果合并。
    """
    try:
        start_time = time.time()
        
        # 执行搜索
        results = await aggregator.search_all(
            query=request.query,
            sources=request.sources,
            limit=request.limit,
            **request.filters
        )
        
        # 去重处理
        if request.deduplicate:
            results = await aggregator.deduplicate_results(results)
        
        # 构建响应
        search_time = time.time() - start_time
        
        metadata = SearchMetadata(
            total_results=len(results.articles),
            sources_searched=[source.value for source in request.sources],
            search_time=search_time,
            duplicates_removed=results.duplicates_removed
        )
        
        return SearchResponse(
            articles=results.articles,
            metadata=metadata
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")

@router.get("/search/history")
async def get_search_history(
    limit: int = 50,
    offset: int = 0,
    db_session = Depends(get_db_session)
):
    """
    获取搜索历史
    
    返回用户的搜索历史记录。
    """
    try:
        # TODO: 实现搜索历史查询
        # history = await db_session.get_search_history(limit=limit, offset=offset)
        
        return {
            "status": "success",
            "history": [],
            "total": 0,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取搜索历史失败: {str(e)}")

@router.post("/search/save")
async def save_search(
    request: SearchRequest,
    db_session = Depends(get_db_session)
):
    """
    保存搜索查询
    
    将搜索查询保存到历史记录中。
    """
    try:
        # TODO: 实现搜索保存功能
        # await db_session.save_search_query(request)
        
        return {
            "status": "success",
            "message": "搜索查询已保存"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存搜索失败: {str(e)}")

@router.get("/search/suggestions")
async def get_search_suggestions(
    query: str,
    limit: int = 10
):
    """
    获取搜索建议
    
    基于查询字符串返回搜索建议。
    """
    try:
        # TODO: 实现搜索建议功能
        suggestions = []
        
        return {
            "status": "success",
            "suggestions": suggestions,
            "query": query
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取搜索建议失败: {str(e)}")

@router.post("/search/validate")
async def validate_search_query(request: SearchRequest):
    """
    验证搜索查询
    
    检查搜索查询的语法和有效性。
    """
    try:
        # TODO: 实现查询验证逻辑
        is_valid = True
        errors = []
        
        return {
            "status": "success",
            "is_valid": is_valid,
            "errors": errors,
            "query": request.query
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证查询失败: {str(e)}")