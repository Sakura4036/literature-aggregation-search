# 文献聚合搜索系统架构设计文档

## 1. 系统概述

### 1.1 项目简介

文献聚合搜索系统是一个综合性的学术文献检索和管理平台，旨在为研究人员提供跨多个学术数据库的统一搜索体验。系统支持PubMed、ArXiv、bioRxiv、Semantic Scholar、Web of Science等主流学术数据库的同步搜索，并提供智能去重、数据聚合、结构化存储等功能。

### 1.2 核心功能

- **多源聚合搜索**: 一键搜索多个文献数据库并聚合结果
- **智能去重合并**: 基于DOI、PMID、ArXiv ID等标识符的文献去重
- **PubMed深度搜索**: 支持MeSH主题词搜索和大规模结果分页处理
- **结构化数据存储**: 统一的数据库设计支持复杂查询和分析
- **高级搜索语法**: 支持布尔运算符(AND、OR、NOT)和复杂表达式
- **数据导出**: 支持JSON格式的结构化数据导出

### 1.3 技术栈

- **后端语言**: Python 3.13
- **Web框架**: FastAPI (异步高性能API框架)
- **数据库**: PostgreSQL 15+ (关系型数据库)
- **ORM**: SQLAlchemy 2.0 (异步支持)
- **核心依赖**: httpx, arxiv, lxml, pydantic
- **CLI工具**: Click (命令行界面)
- **API集成**: PubMed E-utilities, ArXiv API, Semantic Scholar API, bioRxiv API, Web of Science API

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        接口层 (Interface Layer)                  │
│  ┌─────────────────┐                    ┌─────────────────┐      │
│  │   FastAPI       │                    │   CLI Scripts   │      │
│  │   RESTful API   │                    │   (Click-based) │      │
│  └─────────────────┘                    └─────────────────┘      │
├─────────────────────────────────────────────────────────────────┤
│                        业务逻辑层 (Business Logic)               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │   搜索聚合器     │  │   数据处理器     │  │   查询引擎       │  │
│  │ (Search         │  │ (Data           │  │ (Query          │  │
│  │  Aggregator)    │  │  Processor)     │  │  Engine)        │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                        数据访问层 (Data Access)                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │   API适配器      │  │   响应格式化器   │  │   数据库访问器   │  │
│  │ (API Adapters)  │  │ (Response       │  │ (SQLAlchemy     │  │
│  │   (httpx)       │  │  Formatter)     │  │   Async ORM)    │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                        外部服务层 (External Services)            │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │
│  │ PubMed  │ │  ArXiv  │ │ bioRxiv │ │Semantic │ │   WoS   │    │
│  │   API   │ │   API   │ │   API   │ │Scholar  │ │   API   │    │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                        ┌─────────────────┐
                        │ PostgreSQL数据库 │
                        │   (统一数据模型) │
                        └─────────────────┘
```

### 2.2 模块架构

#### 2.2.1 核心模块结构

```
src/
├── api/                       # FastAPI接口模块
│   ├── __init__.py
│   ├── main.py               # FastAPI应用入口
│   ├── routes/               # 路由模块
│   │   ├── __init__.py
│   │   ├── search.py         # 搜索相关路由
│   │   ├── articles.py       # 文章管理路由
│   │   └── export.py         # 数据导出路由
│   ├── dependencies.py       # 依赖注入
│   ├── middleware.py         # 中间件
│   └── schemas.py            # Pydantic数据模型
├── search/                    # 搜索模块
│   ├── __init__.py
│   ├── engine/               # 文献搜索引擎
│   ├── response_formatter.py # 响应格式化器
│   ├── aggregator.py         # 搜索聚合器
│   └── utils.py              # 搜索工具函数
├── database/                  # 数据库模块
│   ├── __init__.py
│   ├── models.py             # SQLAlchemy数据模型
│   ├── connection.py         # 异步数据库连接
│   ├── operations.py         # 异步CRUD操作
│   └── query_builder.py      # 查询构建器
├── processing/                # 数据处理模块
│   ├── __init__.py
│   ├── deduplicator.py       # 去重处理器
│   ├── merger.py             # 数据合并器
│   └── validator.py          # 数据验证器
├── download/                  # 下载模块
│   ├── __init__.py
│   ├── paper_pdf_downloader.py
│   └── utils.py
└── configs.py                 # 配置管理
scripts/                       # CLI脚本模块
├── __init__.py
├── cli.py                    # 主CLI入口 (Click)
├── search_cli.py             # 搜索命令
├── database_cli.py           # 数据库管理命令
└── export_cli.py             # 导出命令
```

## 3. 详细设计

### 3.1 搜索聚合器 (Search Aggregator)

#### 3.1.1 设计目标

- 统一多个数据源的搜索接口
- 并行执行搜索请求以提高效率
- 处理各数据源的错误和超时情况
- 支持搜索结果的实时进度反馈

#### 3.1.2 核心类设计

```python
from typing import Dict, List, Optional
from pydantic import BaseModel
import httpx

class SearchAggregator:
    """搜索聚合器 - 统一管理多数据源搜索"""
    
    def __init__(self, http_client: httpx.AsyncClient):
        self.http_client = http_client
        self.search_apis = {
            'pubmed': PubmedSearchAPI(http_client),
            'arxiv': ArxivSearchAPI(http_client),
            'biorxiv': BioRxivSearchAPI(http_client),
            'semantic_scholar': SemanticBulkSearchAPI(http_client),
            'wos': WosSearchAPI(http_client)
        }
        self.formatter = ResponseFormatter()
    
    async def search_all(self, query: str, **kwargs) -> AggregatedResults:
        """异步并行搜索所有数据源"""
        pass
    
    async def search_selected(self, query: str, sources: List[str], **kwargs) -> AggregatedResults:
        """异步搜索指定数据源"""
        pass
    
    async def merge_results(self, results: Dict[str, List]) -> List[Dict]:
        """合并和去重搜索结果"""
        pass

class AggregatedResults(BaseModel):
    """聚合搜索结果模型"""
    articles: List[Dict]
    metadata: Dict
    sources_searched: List[str]
    total_results: int
    search_time: float
    duplicates_removed: int
```

#### 3.1.3 搜索流程

```
用户查询 → 查询解析 → 并行搜索 → 结果格式化 → 去重合并 → 返回结果
    ↓           ↓         ↓         ↓         ↓         ↓
  验证参数   → 构建请求 → API调用 → 统一格式 → 智能去重 → JSON输出
```

### 3.2 数据处理模块

#### 3.2.1 去重处理器 (Deduplicator)

```python
class Deduplicator:
    """文献去重处理器"""
    
    IDENTIFIER_PRIORITY = ['doi', 'pmid', 'arxiv_id', 'semantic_scholar_id']
    
    def deduplicate(self, articles: List[Dict]) -> List[Dict]:
        """基于标识符的去重算法"""
        pass
    
    def fuzzy_match(self, article1: Dict, article2: Dict) -> float:
        """基于标题和作者的模糊匹配"""
        pass
```

#### 3.2.2 数据合并器 (Merger)

```python
class DataMerger:
    """数据合并器 - 合并来自不同数据源的同一文献信息"""
    
    def merge_articles(self, duplicates: List[Dict]) -> Dict:
        """合并重复文献的信息"""
        pass
    
    def select_best_field(self, field_name: str, values: List) -> Any:
        """选择最佳字段值"""
        pass
```

### 3.3 数据库设计实现

#### 3.3.1 数据模型 (基于database_design.md)

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from typing import Optional
import datetime

class Base(AsyncAttrs, DeclarativeBase):
    """异步SQLAlchemy基类"""
    pass

class Article(Base):
    """文章主表"""
    __tablename__ = 'articles'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    primary_doi: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[Optional[str]] = mapped_column(Text)
    publication_year: Mapped[Optional[int]]
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow, 
        onupdate=datetime.datetime.utcnow
    )
    # ... 其他字段
```

#### 3.3.2 查询构建器

```python
class QueryBuilder:
    """高级查询构建器 - 支持复杂搜索表达式"""
    
    def parse_expression(self, expression: str) -> QueryNode:
        """解析布尔表达式 (AND, OR, NOT, 括号)"""
        pass
    
    def build_sql(self, query_node: QueryNode) -> str:
        """构建SQL查询"""
        pass
```

### 3.4 FastAPI接口设计

#### 3.4.1 RESTful API端点

```python
# FastAPI路由定义
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional

# 搜索相关API
@router.post("/api/v1/search", response_model=SearchResponse)
async def multi_source_search(request: SearchRequest):
    """多源聚合搜索"""
    pass

@router.get("/api/v1/articles/{article_id}", response_model=ArticleDetail)
async def get_article(article_id: int):
    """获取文章详情"""
    pass

@router.post("/api/v1/articles/batch", response_model=List[ArticleDetail])
async def get_articles_batch(article_ids: List[int]):
    """批量获取文章"""
    pass

@router.get("/api/v1/search/history", response_model=List[SearchHistory])
async def get_search_history():
    """搜索历史"""
    pass

@router.post("/api/v1/export", response_model=ExportResponse)
async def export_data(request: ExportRequest, background_tasks: BackgroundTasks):
    """异步数据导出"""
    pass
```

#### 3.4.2 Pydantic数据模型

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class SearchRequest(BaseModel):
    """搜索请求模型"""
    query: str = Field(..., description="搜索查询字符串")
    sources: Optional[List[str]] = Field(
        default=["pubmed", "arxiv", "semantic_scholar"], 
        description="要搜索的数据源列表"
    )
    filters: Optional[Dict[str, Any]] = Field(default={}, description="搜索过滤器")
    limit: int = Field(default=100, ge=1, le=10000, description="结果数量限制")
    deduplicate: bool = Field(default=True, description="是否去重")

class SearchResponse(BaseModel):
    """搜索响应模型"""
    status: str = Field(..., description="响应状态")
    articles: List[Dict[str, Any]] = Field(..., description="文章列表")
    metadata: Dict[str, Any] = Field(..., description="搜索元数据")
    
class ArticleDetail(BaseModel):
    """文章详情模型"""
    id: int
    title: str
    abstract: Optional[str]
    authors: List[str]
    publication_year: Optional[int]
    doi: Optional[str]
    sources: List[str]
    created_at: datetime
    
class ExportRequest(BaseModel):
    """导出请求模型"""
    format: str = Field(..., regex="^(json|csv|bibtex)$")
    article_ids: Optional[List[int]] = None
    search_query: Optional[str] = None
```

## 4. 性能优化策略

### 4.1 异步并发处理

- FastAPI原生异步支持，使用asyncio实现高并发
- httpx异步HTTP客户端处理外部API调用
- SQLAlchemy异步ORM处理数据库操作
- 异步任务队列处理后台任务

### 4.2 缓存策略

- Redis缓存热门查询结果和会话数据
- 应用层缓存API响应数据
- PostgreSQL查询结果缓存
- FastAPI响应缓存中间件

### 4.3 数据库优化

- PostgreSQL索引策略优化
- 连接池管理 (asyncpg)
- 查询优化和执行计划分析
- 数据库分区和分片策略

## 5. 错误处理和监控

### 5.1 错误处理策略

- API请求失败的重试机制
- 优雅降级 (部分数据源失败时继续处理)
- 详细的错误日志记录

### 5.2 监控指标

- API响应时间和成功率
- 数据库查询性能
- 系统资源使用情况
- 用户搜索行为分析

## 6. 安全考虑

### 6.1 API安全

- 请求频率限制
- API密钥管理
- 输入验证和SQL注入防护

### 6.2 数据安全

- 敏感信息加密存储
- 访问权限控制
- 数据备份和恢复策略

## 7. 部署架构

### 7.1 容器化部署

```yaml
# docker-compose.yml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/literature_db
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis
    command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000
  
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: literature_db
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

### 7.2 CLI工具设计

#### 7.2.1 Click命令行界面

```python
# scripts/cli.py
import click
from typing import List, Optional

@click.group()
def cli():
    """文献聚合搜索系统CLI工具"""
    pass

@cli.command()
@click.option('--query', '-q', required=True, help='搜索查询')
@click.option('--sources', '-s', multiple=True, help='数据源')
@click.option('--limit', '-l', default=100, help='结果限制')
@click.option('--output', '-o', help='输出文件')
def search(query: str, sources: tuple, limit: int, output: Optional[str]):
    """执行文献搜索"""
    pass

@cli.command()
@click.option('--format', '-f', type=click.Choice(['json', 'csv', 'bibtex']))
@click.option('--output', '-o', required=True, help='输出文件')
def export(format: str, output: str):
    """导出数据"""
    pass

@cli.group()
def db():
    """数据库管理命令"""
    pass

@db.command()
def init():
    """初始化数据库"""
    pass

@db.command()
def migrate():
    """执行数据库迁移"""
    pass
```

### 7.3 扩展性设计

- FastAPI微服务架构支持独立扩展
- 负载均衡器分发API请求
- PostgreSQL读写分离和分片
- 异步任务队列处理大规模数据

## 8. 开发和测试

### 8.1 开发环境

- Python虚拟环境管理
- 代码质量检查 (pylint, black)
- 单元测试和集成测试

### 8.2 CI/CD流程

- 自动化测试流水线
- 代码覆盖率检查
- 自动化部署脚本

这个架构设计为文献聚合搜索系统提供了完整的技术框架，支持高性能、高可用的学术文献检索和管理功能。
