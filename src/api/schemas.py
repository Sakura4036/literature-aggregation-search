"""
Pydantic数据模型定义
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, date
from enum import Enum

class DataSource(str, Enum):
    """数据源枚举"""
    PUBMED = "pubmed"
    ARXIV = "arxiv"
    BIORXIV = "biorxiv"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    WEB_OF_SCIENCE = "web_of_science"

class ExportFormat(str, Enum):
    """导出格式枚举"""
    JSON = "json"
    CSV = "csv"
    BIBTEX = "bibtex"

class SearchRequest(BaseModel):
    """搜索请求模型"""
    query: str = Field(..., description="搜索查询字符串", min_length=1)
    sources: Optional[List[DataSource]] = Field(
        default=[DataSource.PUBMED, DataSource.ARXIV, DataSource.SEMANTIC_SCHOLAR],
        description="要搜索的数据源列表"
    )
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="搜索过滤器")
    limit: int = Field(default=100, ge=1, le=10000, description="结果数量限制")
    deduplicate: bool = Field(default=True, description="是否去重")
    
    @validator('sources')
    def validate_sources(cls, v):
        if not v:
            raise ValueError("至少需要选择一个数据源")
        return v

class SearchMetadata(BaseModel):
    """搜索元数据"""
    total_results: int = Field(..., description="总结果数")
    sources_searched: List[str] = Field(..., description="已搜索的数据源")
    search_time: float = Field(..., description="搜索耗时(秒)")
    duplicates_removed: int = Field(default=0, description="去重数量")
    query_timestamp: datetime = Field(default_factory=datetime.utcnow, description="查询时间")

class ExportRequest(BaseModel):
    """导出请求模型"""
    format: ExportFormat = Field(..., description="导出格式")
    article_ids: Optional[List[int]] = Field(None, description="指定文章ID列表")
    search_query: Optional[str] = Field(None, description="搜索查询")
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="过滤条件")
    
    @validator('article_ids', 'search_query')
    def validate_export_criteria(cls, v, values):
        article_ids = values.get('article_ids')
        search_query = values.get('search_query')
        if not article_ids and not search_query:
            raise ValueError("必须指定article_ids或search_query之一")
        return v

class ExportResponse(BaseModel):
    """导出响应模型"""
    status: str = Field(default="success", description="导出状态")
    download_url: Optional[str] = Field(None, description="下载链接")
    file_size: Optional[int] = Field(None, description="文件大小(字节)")
    record_count: int = Field(..., description="导出记录数")
    format: str = Field(..., description="导出格式")

class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: str = Field(..., description="错误信息")
    status_code: int = Field(..., description="状态码")
    details: Optional[Dict[str, Any]] = Field(None, description="错误详情")

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="服务状态")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="检查时间")
    version: str = Field(default="1.0.0", description="API版本")

# CLI相关模型
class CLISearchOptions(BaseModel):
    """CLI搜索选项"""
    query: str
    sources: List[str] = Field(default_factory=lambda: ["pubmed", "arxiv"])
    limit: int = 100
    output_file: Optional[str] = None
    format: str = "json"
    verbose: bool = False

class CLIExportOptions(BaseModel):
    """CLI导出选项"""
    format: ExportFormat
    output_file: str
    article_ids: Optional[List[int]] = None
    search_query: Optional[str] = None