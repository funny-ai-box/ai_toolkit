# app/core/database/session.py
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.core.config.settings import settings

# 创建异步数据库引擎
# pool_recycle: 自动回收连接的时间（秒），防止连接因长时间空闲而被MySQL服务器断开
# pool_pre_ping: 在从连接池获取连接时，先发送一个简单的 PING 查询以检查连接是否仍然有效
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    pool_recycle=3600, # 1小时回收一次
    pool_pre_ping=True,
    # 可以根据需要调整连接池大小
    # pool_size=10,
    # max_overflow=20
)

# 创建异步会话工厂
# expire_on_commit=False: 防止在提交后访问对象时出现 DetachedInstanceError，特别是在后台任务中
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False, # 建议在异步代码中关闭自动 flush
)

# SQLAlchemy 模型基类
Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖项，用于获取数据库会话。
    每个请求将获得一个独立的会话，并在请求结束后自动关闭。
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            # 注意：服务层或仓库层应该负责调用 session.commit()
            # 这里不自动提交，让业务逻辑控制事务边界
            # await session.commit() # 不在这里提交
        except Exception:
            await session.rollback() # 如果发生异常则回滚
            raise # 重新抛出异常，让全局异常处理器捕获
        finally:
            await session.close() # 确保会话关闭