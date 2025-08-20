"""
异步数据库连接管理
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging

from .models import Base
from ..configs import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class AsyncDatabaseManager:
    """异步数据库管理器"""
    
    def __init__(self, database_url: str):
        """
        初始化数据库管理器
        
        Args:
            database_url: 数据库连接URL
        """
        self.database_url = database_url
        self.engine = create_async_engine(
            database_url,
            echo=settings.debug,  # 开发环境显示SQL
            poolclass=NullPool if "sqlite" in database_url else None,
            pool_pre_ping=True,
            pool_recycle=3600,  # 1小时回收连接
        )
        
        self.async_session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False
        )
    
    async def create_tables(self):
        """创建所有数据库表"""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("数据库表创建成功")
        except Exception as e:
            logger.error(f"创建数据库表失败: {str(e)}")
            raise
    
    async def drop_tables(self):
        """删除所有数据库表"""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            logger.info("数据库表删除成功")
        except Exception as e:
            logger.error(f"删除数据库表失败: {str(e)}")
            raise
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        获取数据库会话上下文管理器
        
        使用示例:
        async with db_manager.get_session() as session:
            result = await session.execute(select(Article))
        """
        async with self.async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def get_session_direct(self) -> AsyncSession:
        """
        直接获取数据库会话 (需要手动管理)
        
        注意: 使用后需要手动关闭会话
        """
        return self.async_session_factory()
    
    async def close(self):
        """关闭数据库连接"""
        try:
            await self.engine.dispose()
            logger.info("数据库连接已关闭")
        except Exception as e:
            logger.error(f"关闭数据库连接失败: {str(e)}")
    
    async def health_check(self) -> bool:
        """数据库健康检查"""
        try:
            async with self.get_session() as session:
                await session.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"数据库健康检查失败: {str(e)}")
            return False

# 全局数据库管理器实例
_db_manager: AsyncDatabaseManager = None

def get_db_manager() -> AsyncDatabaseManager:
    """获取全局数据库管理器实例"""
    global _db_manager
    if _db_manager is None:
        _db_manager = AsyncDatabaseManager(settings.database_url)
    return _db_manager

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI依赖注入函数 - 获取数据库会话
    
    使用示例:
    @app.get("/articles")
    async def get_articles(db: AsyncSession = Depends(get_db_session)):
        result = await db.execute(select(Article))
        return result.scalars().all()
    """
    db_manager = get_db_manager()
    async with db_manager.get_session() as session:
        yield session

# 数据库初始化函数
async def init_database():
    """初始化数据库"""
    db_manager = get_db_manager()
    await db_manager.create_tables()
    logger.info("数据库初始化完成")

# 数据库清理函数
async def cleanup_database():
    """清理数据库连接"""
    global _db_manager
    if _db_manager:
        await _db_manager.close()
        _db_manager = None