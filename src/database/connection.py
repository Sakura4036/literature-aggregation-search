"""
异步数据库连接管理 (函数式重构)
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging

from .models import Base
from ..configs import app_config

logger = logging.getLogger(__name__)

_engine = None
_async_session_factory = None

def setup_database_engine(database_url: str) -> None:
    global _engine, _async_session_factory
    if not database_url:
        raise ValueError("数据库连接URL不能为空")
    _engine = create_async_engine(
        database_url,
        echo=app_config.DEBUG,
        poolclass=NullPool if "sqlite" in database_url else None,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    _async_session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=True,
        autocommit=False
    )
    logger.info("数据库引擎和会话工厂初始化完成")

setup_database_engine(app_config.SQLALCHEMY_DATABASE_URI)

@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    if _async_session_factory is None:
        raise RuntimeError("数据库会话工厂未初始化")
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"数据库会话异常: {str(e)}")
            raise
        finally:
            await session.close()

async def create_tables() -> None:
    if _engine is None:
        raise RuntimeError("数据库引擎未初始化")
    try:
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表创建成功")
    except Exception as e:
        logger.error(f"创建数据库表失败: {str(e)}")
        raise

async def drop_tables() -> None:
    if _engine is None:
        raise RuntimeError("数据库引擎未初始化")
    try:
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("数据库表删除成功")
    except Exception as e:
        logger.error(f"删除数据库表失败: {str(e)}")
        raise

async def close_database() -> None:
    global _engine, _async_session_factory
    if _engine:
        try:
            await _engine.dispose()
            logger.info("数据库连接已关闭")
        except Exception as e:
            logger.error(f"关闭数据库连接失败: {str(e)}")
    _engine = None
    _async_session_factory = None

async def health_check() -> bool:
    try:
        async with get_db_session() as session:
            await session.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"数据库健康检查失败: {str(e)}")
        return False

DbSession = get_db_session

async def init_database() -> None:
    await create_tables()
    logger.info("数据库初始化完成")

async def cleanup_database() -> None:
    await close_database()