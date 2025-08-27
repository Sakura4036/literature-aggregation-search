# 增强数据库实现设计文档

## 概述

本设计文档描述了增强数据库实现的技术方案，包括UUID主键转换、任务管理系统、文件存储管理、搜索结果格式统一，以及遵循FastAPI最佳实践的完整数据访问层实现。

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI应用层                             │
├─────────────────────────────────────────────────────────────┤
│                    服务层 (Services)                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │  文献服务        │  │  任务服务        │  │  文件服务     │ │
│  │  LiteratureService│  │  TaskService    │  │  FileService │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                    仓储层 (Repositories)                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │  文献仓储        │  │  任务仓储        │  │  文件仓储     │ │
│  │  LiteratureRepo │  │  TaskRepository │  │  FileRepo    │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                 数据模型层 (SQLAlchemy + UUID)               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   核心模型       │  │   任务模型       │  │  文件模型     │ │
│  │   (UUID主键)     │  │   (UUID主键)     │  │  (UUID主键)  │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                PostgreSQL数据库 (UUID + JSONB)              │
└─────────────────────────────────────────────────────────────┘
```

### 技术栈

- **数据库**: PostgreSQL 15+ (UUID, JSONB, 异步支持)
- **ORM**: SQLAlchemy 2.0 (异步)
- **数据验证**: Pydantic v2
- **任务队列**: Celery + Redis
- **文件存储**: 本地文件系统 + 数据库元数据
- **连接池**: asyncpg

## UUID主键转换设计

### UUID生成策略

```python
import uuid
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

class UUIDMixin:
    """UUID主键混入类"""
    id = Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4,
        server_default=func.gen_random_uuid()
    )
```

### 迁移策略

```python
# 迁移脚本示例
def upgrade():
    # 1. 添加新的UUID列
    op.add_column('articles', sa.Column('id_new', UUID(as_uuid=True), nullable=True))
    
    # 2. 为现有记录生成UUID
    op.execute("UPDATE articles SET id_new = gen_random_uuid()")
    
    # 3. 更新外键引用
    # ... 外键更新逻辑
    
    # 4. 删除旧列，重命名新列
    op.drop_column('articles', 'id')
    op.alter_column('articles', 'id_new', new_column_name='id')
```

## 任务管理系统设计

### 任务模型设计

```python
from enum import Enum
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running" 
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    CANCELLED = "cancelled"

class TaskType(str, Enum):
    LITERATURE_SEARCH = "literature_search"
    PDF_DOWNLOAD = "pdf_download"
    DATA_EXPORT = "data_export"
    BATCH_IMPORT = "batch_import"

class Task(Base, UUIDMixin):
    __tablename__ = 'tasks'
    
    task_type = Column(Enum(TaskType), nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    celery_task_id = Column(String(255), unique=True, index=True)
    
    # 任务参数和结果
    parameters = Column(JSONB)  # 任务输入参数
    result = Column(JSONB)      # 任务执行结果
    error_message = Column(Text)
    
    # 进度跟踪
    progress_current = Column(Integer, default=0)
    progress_total = Column(Integer, default=100)
    progress_message = Column(String(500))
    
    # 重试机制
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # 关联用户（如果需要）
    user_id = Column(UUID(as_uuid=True), nullable=True)

class SearchTask(Base, UUIDMixin):
    __tablename__ = 'search_tasks'
    
    task_id = Column(UUID(as_uuid=True), ForeignKey('tasks.id'), nullable=False)
    
    # 搜索参数
    query = Column(Text, nullable=False)
    data_sources = Column(JSONB)  # 选择的数据源列表
    filters = Column(JSONB)       # 搜索过滤条件
    
    # 搜索结果统计
    total_results = Column(Integer, default=0)
    saved_articles = Column(Integer, default=0)
    duplicate_articles = Column(Integer, default=0)
    
    task = relationship("Task", backref="search_details")

class DownloadTask(Base, UUIDMixin):
    __tablename__ = 'download_tasks'
    
    task_id = Column(UUID(as_uuid=True), ForeignKey('tasks.id'), nullable=False)
    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id'), nullable=False)
    
    # 下载参数
    download_url = Column(Text, nullable=False)
    file_type = Column(String(50), default='pdf')
    
    # 下载结果
    file_path = Column(Text)
    file_size = Column(Integer)
    download_duration = Column(Integer)  # 秒
    
    task = relationship("Task", backref="download_details")
    article = relationship("Article", backref="download_tasks")
```

## 文件存储系统设计

### 文件模型设计

```python
class FileType(str, Enum):
    PDF = "pdf"
    MARKDOWN = "markdown"
    SUPPLEMENTARY = "supplementary"
    IMAGE = "image"
    DATA = "data"

class File(Base, UUIDMixin):
    __tablename__ = 'files'
    
    # 文件基本信息
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500))
    file_type = Column(Enum(FileType), nullable=False)
    mime_type = Column(String(100))
    file_size = Column(Integer)  # 字节
    
    # 存储信息
    storage_path = Column(Text, nullable=False)  # 相对路径
    storage_backend = Column(String(50), default='local')  # 存储后端
    
    # 文件哈希（用于去重）
    file_hash = Column(String(64), index=True)  # SHA-256
    
    # 元数据
    metadata = Column(JSONB)  # 额外的文件元数据
    
    # 版本控制
    version = Column(Integer, default=1)
    parent_file_id = Column(UUID(as_uuid=True), ForeignKey('files.id'))
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关联关系
    parent_file = relationship("File", remote_side=[id])
    versions = relationship("File", remote_side=[parent_file_id])

class ArticleFile(Base, UUIDMixin):
    __tablename__ = 'article_files'
    
    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id'), nullable=False)
    file_id = Column(UUID(as_uuid=True), ForeignKey('files.id'), nullable=False)
    
    # 关联类型
    relationship_type = Column(String(50), nullable=False)  # 'main_pdf', 'supplement', 'note'
    description = Column(Text)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    article = relationship("Article", backref="article_files")
    file = relationship("File", backref="article_associations")
    
    __table_args__ = (
        UniqueConstraint('article_id', 'file_id', name='uq_article_file'),
    )
```

### 文件存储服务

```python
from pathlib import Path
import hashlib
import aiofiles
from typing import Optional, BinaryIO

class FileStorageService:
    def __init__(self, base_path: str = "storage"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
    
    async def save_file(
        self, 
        file_content: bytes, 
        filename: str,
        file_type: FileType,
        article_id: Optional[str] = None
    ) -> File:
        """保存文件并返回文件记录"""
        
        # 计算文件哈希
        file_hash = hashlib.sha256(file_content).hexdigest()
        
        # 检查是否已存在相同文件
        existing_file = await self._find_by_hash(file_hash)
        if existing_file:
            return existing_file
        
        # 生成存储路径
        storage_path = self._generate_storage_path(filename, file_type, article_id)
        full_path = self.base_path / storage_path
        
        # 确保目录存在
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 异步写入文件
        async with aiofiles.open(full_path, 'wb') as f:
            await f.write(file_content)
        
        # 创建数据库记录
        file_record = File(
            filename=full_path.name,
            original_filename=filename,
            file_type=file_type,
            file_size=len(file_content),
            storage_path=str(storage_path),
            file_hash=file_hash
        )
        
        return file_record
    
    def _generate_storage_path(
        self, 
        filename: str, 
        file_type: FileType,
        article_id: Optional[str] = None
    ) -> Path:
        """生成文件存储路径"""
        # 按类型和日期组织文件
        from datetime import datetime
        date_path = datetime.now().strftime("%Y/%m/%d")
        
        if article_id:
            return Path(f"{file_type.value}/{date_path}/{article_id}/{filename}")
        else:
            return Path(f"{file_type.value}/{date_path}/{filename}")
```

## 搜索结果格式统一设计

### 统一Schema设计

```python
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from uuid import UUID

class LiteratureSchema(BaseModel):
    """统一的文献数据Schema"""
    
    # 基本信息
    title: str
    abstract: Optional[str] = None
    language: str = "eng"
    publication_year: Optional[int] = None
    publication_date: Optional[date] = None
    
    # 统计信息
    citation_count: int = 0
    reference_count: int = 0
    influential_citation_count: int = 0
    
    # 开放获取
    is_open_access: bool = False
    open_access_url: Optional[str] = None
    
    # 标识符
    identifiers: List[IdentifierSchema] = Field(default_factory=list)
    
    # 作者
    authors: List[AuthorSchema] = Field(default_factory=list)
    
    # 发表信息
    venue: Optional[VenueSchema] = None
    
    # 分类
    categories: List[CategorySchema] = Field(default_factory=list)
    
    # 数据源信息
    source_info: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True
        validate_assignment = True
    
    def to_article_model(self) -> Article:
        """转换为Article数据库模型"""
        article = Article(
            title=self.title,
            abstract=self.abstract,
            language=self.language,
            publication_year=self.publication_year,
            publication_date=self.publication_date,
            citation_count=self.citation_count,
            reference_count=self.reference_count,
            influential_citation_count=self.influential_citation_count,
            is_open_access=self.is_open_access,
            open_access_url=self.open_access_url
        )
        
        # 设置主DOI
        primary_doi = self.get_primary_identifier(IdentifierType.DOI)
        if primary_doi:
            article.primary_doi = primary_doi
        
        return article
    
    @classmethod
    def from_article_model(cls, article: Article) -> 'LiteratureSchema':
        """从Article模型创建Schema"""
        return cls(
            title=article.title,
            abstract=article.abstract,
            language=article.language,
            publication_year=article.publication_year,
            publication_date=article.publication_date,
            citation_count=article.citation_count,
            reference_count=article.reference_count,
            influential_citation_count=article.influential_citation_count,
            is_open_access=article.is_open_access,
            open_access_url=article.open_access_url,
            identifiers=[
                IdentifierSchema.from_model(identifier) 
                for identifier in article.identifiers
            ],
            authors=[
                AuthorSchema.from_model(author_assoc) 
                for author_assoc in article.authors
            ]
        )
```

## 数据访问层设计

### 基础仓储模式

```python
from abc import ABC, abstractmethod
from typing import List, Optional, TypeVar, Generic
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from uuid import UUID

T = TypeVar('T')

class BaseRepository(Generic[T], ABC):
    def __init__(self, session: AsyncSession, model_class: type):
        self.session = session
        self.model_class = model_class
    
    async def create(self, **kwargs) -> T:
        """创建新记录"""
        instance = self.model_class(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance
    
    async def get_by_id(self, id: UUID) -> Optional[T]:
        """根据UUID获取记录"""
        result = await self.session.execute(
            select(self.model_class).where(self.model_class.id == id)
        )
        return result.scalar_one_or_none()
    
    async def update(self, id: UUID, **kwargs) -> Optional[T]:
        """更新记录"""
        await self.session.execute(
            update(self.model_class)
            .where(self.model_class.id == id)
            .values(**kwargs)
        )
        return await self.get_by_id(id)
    
    async def delete(self, id: UUID) -> bool:
        """删除记录"""
        result = await self.session.execute(
            delete(self.model_class).where(self.model_class.id == id)
        )
        return result.rowcount > 0
    
    async def list_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """分页获取所有记录"""
        result = await self.session.execute(
            select(self.model_class)
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()
```

### 文献仓储实现

```python
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import and_, or_, func

class LiteratureRepository(BaseRepository[Article]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Article)
    
    async def find_by_identifier(
        self, 
        identifier_type: IdentifierType, 
        identifier_value: str
    ) -> Optional[Article]:
        """根据标识符查找文章"""
        result = await self.session.execute(
            select(Article)
            .join(ArticleIdentifier)
            .where(
                and_(
                    ArticleIdentifier.identifier_type == identifier_type,
                    ArticleIdentifier.identifier_value == identifier_value
                )
            )
            .options(
                selectinload(Article.identifiers),
                selectinload(Article.authors).selectinload(ArticleAuthor.author),
                selectinload(Article.sources)
            )
        )
        return result.scalar_one_or_none()
    
    async def create_from_schema(self, literature: LiteratureSchema) -> Article:
        """从LiteratureSchema创建完整的文章记录"""
        # 检查重复
        duplicates = await self.find_duplicates(literature)
        if duplicates:
            return await self.merge_literature(duplicates[0], literature)
        
        # 创建新文章
        article = literature.to_article_model()
        self.session.add(article)
        await self.session.flush()
        
        # 创建标识符
        for identifier_data in literature.identifiers:
            identifier = ArticleIdentifier(
                article_id=article.id,
                identifier_type=identifier_data.identifier_type,
                identifier_value=identifier_data.identifier_value,
                is_primary=identifier_data.is_primary
            )
            self.session.add(identifier)
        
        # 创建作者关联
        for i, author_data in enumerate(literature.authors):
            author = await self._find_or_create_author(author_data)
            
            article_author = ArticleAuthor(
                article_id=article.id,
                author_id=author.id,
                author_order=author_data.author_order or i + 1,
                is_corresponding=author_data.is_corresponding
            )
            self.session.add(article_author)
        
        await self.session.flush()
        return article
    
    async def find_duplicates(self, literature: LiteratureSchema) -> List[Article]:
        """查找重复文献"""
        duplicates = []
        
        # 基于标识符的精确匹配
        for identifier in literature.identifiers:
            if identifier.identifier_value:
                existing = await self.find_by_identifier(
                    identifier.identifier_type,
                    identifier.identifier_value
                )
                if existing:
                    duplicates.append(existing)
        
        # 基于标题的模糊匹配（如果没有精确匹配）
        if not duplicates and literature.title:
            title_matches = await self.search_by_title_similarity(
                literature.title, 
                threshold=0.8
            )
            duplicates.extend(title_matches)
        
        return list(set(duplicates))
```

## 服务层设计

### 模块化服务架构

每个实体使用独立的服务模块，遵循单一职责原则：

```
src/services/
├── __init__.py
├── article_service.py      # 文章CRUD服务
├── author_service.py       # 作者CRUD服务
├── task_service.py         # 任务管理服务
├── file_service.py         # 文件管理服务
├── literature_service.py   # 文献聚合服务（跨实体操作）
└── query_service.py        # 复杂查询服务
```

### 文章服务

```python
# src/services/article_service.py
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from src.schemas.article_schemas import ArticleCreateSchema, ArticleUpdateSchema, ArticleResponseSchema
from src.repositories.article_repository import ArticleRepository
from src.models.models import Article

async def create_article(
    article_data: ArticleCreateSchema,
    db_session: AsyncSession
) -> ArticleResponseSchema:
    """创建新文章"""
    # 数据验证
    try:
        validated_data = article_data.model_validate(article_data.model_dump())
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {e}")
    
    repo = ArticleRepository(db_session)
    
    try:
        article = await repo.create(**validated_data.model_dump(exclude_unset=True))
        await db_session.commit()
        return ArticleResponseSchema.from_orm(article)
    except Exception as e:
        await db_session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create article: {e}")

async def get_article_by_id(
    article_id: UUID,
    db_session: AsyncSession
) -> Optional[ArticleResponseSchema]:
    """根据ID获取文章"""
    repo = ArticleRepository(db_session)
    article = await repo.get_by_id(article_id)
    
    if not article:
        return None
    
    return ArticleResponseSchema.from_orm(article)

async def update_article(
    article_id: UUID,
    update_data: ArticleUpdateSchema,
    db_session: AsyncSession
) -> Optional[ArticleResponseSchema]:
    """更新文章"""
    # 数据验证
    try:
        validated_data = update_data.model_validate(update_data.model_dump())
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {e}")
    
    repo = ArticleRepository(db_session)
    
    try:
        article = await repo.update(article_id, **validated_data.model_dump(exclude_unset=True))
        if not article:
            return None
        
        await db_session.commit()
        return ArticleResponseSchema.from_orm(article)
    except Exception as e:
        await db_session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update article: {e}")

async def delete_article(
    article_id: UUID,
    db_session: AsyncSession
) -> bool:
    """删除文章"""
    repo = ArticleRepository(db_session)
    
    try:
        success = await repo.delete(article_id)
        await db_session.commit()
        return success
    except Exception as e:
        await db_session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete article: {e}")

async def list_articles(
    limit: int = 100,
    offset: int = 0,
    db_session: AsyncSession
) -> List[ArticleResponseSchema]:
    """分页获取文章列表"""
    repo = ArticleRepository(db_session)
    articles = await repo.list_all(limit=limit, offset=offset)
    return [ArticleResponseSchema.from_orm(article) for article in articles]
```

### 作者服务

```python
# src/services/author_service.py
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.author_schemas import AuthorCreateSchema, AuthorUpdateSchema, AuthorResponseSchema
from src.repositories.author_repository import AuthorRepository

async def create_author(
    author_data: AuthorCreateSchema,
    db_session: AsyncSession
) -> AuthorResponseSchema:
    """创建新作者"""
    try:
        validated_data = author_data.model_validate(author_data.model_dump())
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {e}")
    
    repo = AuthorRepository(db_session)
    
    try:
        author = await repo.create(**validated_data.model_dump(exclude_unset=True))
        await db_session.commit()
        return AuthorResponseSchema.from_orm(author)
    except Exception as e:
        await db_session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create author: {e}")

async def find_or_create_author(
    author_data: AuthorCreateSchema,
    db_session: AsyncSession
) -> AuthorResponseSchema:
    """查找或创建作者（用于去重）"""
    repo = AuthorRepository(db_session)
    
    # 尝试根据ORCID或姓名查找
    existing_author = None
    if author_data.orcid:
        existing_author = await repo.find_by_orcid(author_data.orcid)
    
    if not existing_author and author_data.full_name:
        existing_author = await repo.find_by_name_fuzzy(author_data.full_name)
    
    if existing_author:
        return AuthorResponseSchema.from_orm(existing_author)
    
    # 创建新作者
    return await create_author(author_data, db_session)
```

### 任务服务

```python
# src/services/task_service.py
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.task_schemas import TaskCreateSchema, TaskUpdateSchema, TaskResponseSchema
from src.repositories.task_repository import TaskRepository
from src.models.enums import TaskStatus

async def create_task(
    task_data: TaskCreateSchema,
    db_session: AsyncSession
) -> TaskResponseSchema:
    """创建新任务"""
    try:
        validated_data = task_data.model_validate(task_data.model_dump())
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {e}")
    
    repo = TaskRepository(db_session)
    
    try:
        task = await repo.create(**validated_data.model_dump(exclude_unset=True))
        await db_session.commit()
        return TaskResponseSchema.from_orm(task)
    except Exception as e:
        await db_session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create task: {e}")

async def update_task_status(
    task_id: UUID,
    status: TaskStatus,
    result: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    db_session: AsyncSession
) -> Optional[TaskResponseSchema]:
    """更新任务状态"""
    repo = TaskRepository(db_session)
    
    update_data = {"status": status}
    if result is not None:
        update_data["result"] = result
    if error_message:
        update_data["error_message"] = error_message
    
    try:
        task = await repo.update(task_id, **update_data)
        if not task:
            return None
        
        await db_session.commit()
        return TaskResponseSchema.from_orm(task)
    except Exception as e:
        await db_session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update task: {e}")

async def update_task_progress(
    task_id: UUID,
    current: int,
    total: int,
    message: Optional[str] = None,
    db_session: AsyncSession
) -> Optional[TaskResponseSchema]:
    """更新任务进度"""
    update_data = {
        "progress_current": current,
        "progress_total": total
    }
    if message:
        update_data["progress_message"] = message
    
    repo = TaskRepository(db_session)
    
    try:
        task = await repo.update(task_id, **update_data)
        if not task:
            return None
        
        await db_session.commit()
        return TaskResponseSchema.from_orm(task)
    except Exception as e:
        await db_session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update task progress: {e}")
```

### 文献聚合服务

```python
# src/services/literature_service.py
from typing import List, Dict, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.literature_schemas import LiteratureSchema, LiteratureSaveResultSchema
from src.services import article_service, author_service, task_service
from src.repositories.literature_repository import LiteratureRepository

async def save_literature_batch(
    literature_list: List[LiteratureSchema],
    task_id: Optional[UUID] = None,
    db_session: AsyncSession
) -> LiteratureSaveResultSchema:
    """批量保存文献数据（跨实体操作）"""
    stats = LiteratureSaveResultSchema(
        total=len(literature_list),
        saved=0,
        duplicates=0,
        errors=0,
        error_details=[]
    )
    
    literature_repo = LiteratureRepository(db_session)
    
    for i, literature in enumerate(literature_list):
        try:
            # 更新任务进度
            if task_id:
                await task_service.update_task_progress(
                    task_id=task_id,
                    current=i + 1,
                    total=len(literature_list),
                    message=f"Processing: {literature.title[:50]}...",
                    db_session=db_session
                )
            
            # 检查重复
            duplicates = await literature_repo.find_duplicates(literature)
            
            if duplicates:
                # 合并数据
                await merge_literature_data(duplicates[0].id, literature, db_session)
                stats.duplicates += 1
            else:
                # 创建新记录
                await create_literature_complete(literature, db_session)
                stats.saved += 1
            
        except Exception as e:
            stats.errors += 1
            stats.error_details.append({
                'index': i,
                'title': literature.title,
                'error': str(e)
            })
            # 记录错误但继续处理其他记录
            logger.error(f"Error processing literature {i}: {e}")
    
    return stats

async def create_literature_complete(
    literature: LiteratureSchema,
    db_session: AsyncSession
) -> UUID:
    """创建完整的文献记录（包含所有关联数据）"""
    # 1. 创建文章主记录
    article_data = literature.to_article_create_schema()
    article = await article_service.create_article(article_data, db_session)
    
    # 2. 处理作者
    for author_data in literature.authors:
        author = await author_service.find_or_create_author(author_data, db_session)
        # 创建文章-作者关联
        # ... 关联逻辑
    
    # 3. 处理标识符
    # ... 标识符创建逻辑
    
    # 4. 处理其他关联数据
    # ... 其他关联逻辑
    
    return article.id

async def merge_literature_data(
    existing_article_id: UUID,
    new_literature: LiteratureSchema,
    db_session: AsyncSession
) -> None:
    """合并文献数据到现有记录"""
    # 获取现有文章
    existing_article = await article_service.get_article_by_id(existing_article_id, db_session)
    if not existing_article:
        raise ValueError(f"Article {existing_article_id} not found")
    
    # 合并逻辑：选择更完整的数据
    update_data = {}
    
    # 比较和合并各字段
    if new_literature.abstract and len(new_literature.abstract) > len(existing_article.abstract or ''):
        update_data['abstract'] = new_literature.abstract
    
    if new_literature.citation_count > existing_article.citation_count:
        update_data['citation_count'] = new_literature.citation_count
    
    # 更新文章
    if update_data:
        await article_service.update_article(existing_article_id, update_data, db_session)
    
    # 合并其他关联数据（标识符、作者等）
    # ... 合并逻辑
```

### FastAPI依赖注入

```python
# src/dependencies.py
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.connection import get_async_session

async def get_db_session() -> AsyncSession:
    """FastAPI依赖：获取数据库会话"""
    async with get_async_session() as session:
        try:
            yield session
        finally:
            await session.close()

# 在路由中使用
from fastapi import Depends

@app.post("/articles/", response_model=ArticleResponseSchema)
async def create_article_endpoint(
    article_data: ArticleCreateSchema,
    db_session: AsyncSession = Depends(get_db_session)
):
    return await article_service.create_article(article_data, db_session)
```

## 错误处理和日志

### 统一异常处理

```python
class DatabaseError(Exception):
    """数据库操作异常基类"""
    pass

class DuplicateError(DatabaseError):
    """重复数据异常"""
    pass

class ValidationError(DatabaseError):
    """数据验证异常"""
    pass

class FileStorageError(Exception):
    """文件存储异常"""
    pass

# 异常处理装饰器
def handle_database_errors(func):
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except SQLAlchemyError as e:
            logger.error(f"Database error in {func.__name__}: {e}")
            raise DatabaseError(f"Database operation failed: {e}")
        except ValidationError as e:
            logger.error(f"Validation error in {func.__name__}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            raise DatabaseError(f"Unexpected database error: {e}")
    
    return wrapper
```

## 测试策略

### 单元测试设计

```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

@pytest.fixture
async def test_session():
    """测试数据库会话"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()

@pytest.mark.asyncio
async def test_literature_repository_create_from_schema(test_session):
    """测试从Schema创建文献记录"""
    repo = LiteratureRepository(test_session)
    
    literature = LiteratureSchema(
        title="Test Article",
        abstract="Test abstract",
        publication_year=2023,
        identifiers=[
            IdentifierSchema(
                identifier_type=IdentifierType.DOI,
                identifier_value="10.1000/test",
                is_primary=True
            )
        ]
    )
    
    article = await repo.create_from_schema(literature)
    
    assert article.id is not None
    assert article.title == "Test Article"
    assert len(article.identifiers) == 1
    assert article.identifiers[0].identifier_value == "10.1000/test"
```

这个设计提供了完整的增强数据库实现方案，确保了UUID主键、任务管理、文件存储和格式统一的全面支持，同时遵循FastAPI最佳实践。