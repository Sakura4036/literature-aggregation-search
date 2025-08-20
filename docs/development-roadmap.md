# 开发路线图 (Development Roadmap)

## 当前状态评估

### ✅ 已完成功能
1. **搜索API集成**
   - [x] PubMed搜索API (`src/search/pubmed_search.py`)
   - [x] ArXiv搜索API (`src/search/arxiv_search.py`) 
   - [x] bioRxiv搜索API (`src/search/biorxiv_search.py`)
   - [x] Semantic Scholar搜索API (`src/search/semantic_search.py`)
   - [x] Web of Science搜索API (`src/search/wos_search.py`)

2. **数据格式化**
   - [x] 响应格式化器 (`src/search/response_formatter.py`)
   - [x] 统一数据格式定义

3. **数据库设计**
   - [x] 完整的数据库架构设计 (`docs/database_design.md`)
   - [x] 多源数据整合策略
   - [x] 去重和合并规则定义

4. **XML解析**
   - [x] PubMed XML解析器 (`src/search/pubmed_xml_parser.py`)
   - [x] 结构化数据提取

5. **下载功能**
   - [x] PDF下载器基础框架 (`src/download/`)

### 🔄 进行中功能
- 项目架构文档完善
- 开发计划制定

### ❌ 待开发功能
以下是按优先级排序的待开发功能清单：

## Phase 1: 核心搜索聚合 (优先级: 高)

### 1.1 搜索聚合器开发
**文件**: `src/search/aggregator.py`

```python
# 需要实现的核心类
class SearchAggregator:
    def __init__(self):
        # 初始化各搜索API
        pass
    
    async def search_all(self, query: str, **kwargs):
        # 并行搜索所有数据源
        pass
    
    def merge_results(self, results: Dict[str, List]):
        # 合并和去重搜索结果
        pass
```

**预估工作量**: 1周
**依赖**: 现有搜索API

### 1.2 去重处理器
**文件**: `src/processing/deduplicator.py`

```python
class Deduplicator:
    def deduplicate_by_identifiers(self, articles: List[Dict]):
        # 基于DOI、PMID、ArXiv ID去重
        pass
    
    def fuzzy_match(self, article1: Dict, article2: Dict):
        # 标题和作者模糊匹配
        pass
```

**预估工作量**: 1周
**依赖**: 响应格式化器

### 1.3 数据合并器
**文件**: `src/processing/merger.py`

```python
class DataMerger:
    def merge_duplicate_articles(self, duplicates: List[Dict]):
        # 合并重复文献信息
        pass
```

**预估工作量**: 0.5周
**依赖**: 去重处理器

## Phase 2: 数据库实现 (优先级: 高)

### 2.1 数据模型实现
**文件**: `src/database/models.py`

基于 `docs/database_design.md` 实现完整的SQLAlchemy异步模型：
- Article, Author, Venue等核心实体
- 关联表和外键关系
- PostgreSQL特性支持 (JSONB, 全文搜索)
- 异步ORM配置

**预估工作量**: 1.5周
**依赖**: database_design.md

### 2.2 异步数据库连接管理
**文件**: `src/database/connection.py`

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

class AsyncDatabaseManager:
    def __init__(self, connection_string: str):
        self.engine = create_async_engine(connection_string)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def get_session(self) -> AsyncSession:
        # 获取异步数据库会话
        pass
    
    async def create_tables(self):
        # 创建数据库表
        pass
```

**预估工作量**: 0.5周
**依赖**: 数据模型

### 2.3 CRUD操作
**文件**: `src/database/operations.py`

```python
class ArticleOperations:
    def create_article(self, article_data: Dict):
        pass
    
    def find_duplicates(self, identifiers: Dict):
        pass
    
    def update_article(self, article_id: int, data: Dict):
        pass
```

**预估工作量**: 1周
**依赖**: 数据模型, 连接管理

## Phase 3: 查询引擎 (优先级: 中)

### 3.1 查询构建器
**文件**: `src/database/query_builder.py`

```python
class QueryBuilder:
    def parse_boolean_expression(self, expression: str):
        # 解析 AND, OR, NOT 表达式
        pass
    
    def build_search_query(self, criteria: Dict):
        # 构建复杂搜索查询
        pass
```

**预估工作量**: 1.5周
**依赖**: 数据模型

### 3.2 高级搜索接口
**文件**: `src/api/search_api.py`

```python
class AdvancedSearchAPI:
    def boolean_search(self, expression: str):
        # 布尔搜索
        pass
    
    def field_search(self, field: str, value: str):
        # 字段搜索
        pass
```

**预估工作量**: 1周
**依赖**: 查询构建器

## Phase 4: FastAPI和CLI (优先级: 中)

### 4.1 FastAPI应用
**文件**: `src/api/main.py`, `src/api/routes/`

```python
# FastAPI应用结构
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Literature Aggregation API", version="1.0.0")

@app.post('/api/v1/search')
async def multi_source_search(request: SearchRequest):
    pass

@app.get('/api/v1/articles/{article_id}')
async def get_article(article_id: int):
    pass

@app.post('/api/v1/export')
async def export_data(request: ExportRequest):
    pass
```

**预估工作量**: 2周
**依赖**: 搜索聚合器, 数据库操作

### 4.2 CLI工具
**文件**: `scripts/cli.py`, `scripts/search_cli.py`

```python
# Click命令行工具
import click

@click.group()
def cli():
    """文献聚合搜索系统CLI"""
    pass

@cli.command()
@click.option('--query', '-q', required=True)
def search(query: str):
    """执行搜索"""
    pass

@cli.command()
def export():
    """导出数据"""
    pass
```

**预估工作量**: 1周
**依赖**: 搜索聚合器

## Phase 5: 优化和扩展 (优先级: 低)

### 5.1 性能优化
- 异步搜索实现
- 缓存机制
- 数据库查询优化

**预估工作量**: 1周

### 5.2 监控和日志
**文件**: `src/monitoring/`

- 搜索性能监控
- 错误日志记录
- 用户行为分析

**预估工作量**: 1周

### 5.3 数据分析功能
**文件**: `src/analytics/`

- 文献统计分析
- 趋势分析
- 可视化图表

**预估工作量**: 2周

## 立即行动计划

### 本周任务 (Week 1)
1. **创建项目结构**
   ```bash
   mkdir -p src/{processing,database,api/{routes,schemas},monitoring,analytics}
   mkdir -p scripts
   touch src/processing/{__init__.py,deduplicator.py,merger.py,validator.py}
   touch src/database/{__init__.py,models.py,connection.py,operations.py,query_builder.py}
   touch src/api/{__init__.py,main.py,dependencies.py,middleware.py,schemas.py}
   touch src/api/routes/{__init__.py,search.py,articles.py,export.py}
   touch scripts/{__init__.py,cli.py,search_cli.py,database_cli.py,export_cli.py}
   ```

2. **实现异步搜索聚合器**
   - 创建 `src/search/aggregator.py`
   - 实现基于httpx的异步并行搜索功能
   - 集成现有的搜索API

3. **开始去重处理器**
   - 创建 `src/processing/deduplicator.py`
   - 实现基于标识符的精确匹配

### 下周任务 (Week 2)
1. **完善去重和合并功能**
2. **开始数据库模型实现**
3. **编写单元测试**

### 第三周任务 (Week 3)
1. **完成异步数据库CRUD操作**
2. **集成搜索聚合器和PostgreSQL数据库**
3. **实现基本的FastAPI接口和CLI工具**

## 技术债务和改进项

### 现有代码改进
1. **错误处理增强**
   - 统一异常处理机制
   - 更详细的错误日志

2. **配置管理**
   - 环境变量配置
   - API密钥管理

3. **测试覆盖率**
   - 单元测试
   - 集成测试
   - 性能测试

### 代码质量
1. **代码规范**
   - 添加类型注解
   - 文档字符串完善
   - 代码格式化 (black, isort)

2. **依赖管理**
   - 更新 `pyproject.toml`
   - 添加开发依赖
   - 版本锁定

## 部署和运维

### 容器化
```dockerfile
# Dockerfile
FROM python:3.13-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY pyproject.toml uv.lock ./

# 安装Python依赖
RUN pip install uv && uv sync --frozen

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动FastAPI应用
CMD ["uv", "run", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 数据库迁移
```python
# src/database/migrations.py
def create_initial_schema():
    # 创建初始数据库架构
    pass

def migrate_to_v1_1():
    # 版本升级迁移
    pass
```

### 监控指标
- API响应时间
- 搜索成功率
- 数据库查询性能
- 系统资源使用

## 风险缓解

### 技术风险
1. **API限制**: 实现请求频率控制和重试机制
2. **数据质量**: 增加数据验证和清洗流程
3. **性能瓶颈**: 实现缓存和异步处理

### 项目风险
1. **开发延期**: 采用敏捷开发，定期评估进度
2. **需求变更**: 建立需求变更控制流程
3. **质量问题**: 实施代码审查和自动化测试

## 成功指标

### 开发指标
- [ ] 代码覆盖率 > 80%
- [ ] API响应时间 < 30秒
- [ ] 去重准确率 > 95%
- [ ] 系统可用性 > 99%

### 功能指标
- [ ] 支持5个主要数据源
- [ ] 实现智能去重合并
- [ ] 支持10,000+文献处理
- [ ] 提供完整的RESTful API

这个开发路线图为项目提供了清晰的实施路径，确保按优先级有序推进开发工作。