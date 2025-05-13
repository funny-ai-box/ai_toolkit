"""
聊天历史仓储实现
"""
from typing import List, Optional
import datetime
from sqlalchemy import select, delete, and_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.core.utils.snowflake import generate_id
from app.modules.tools.pkb.models import ChatHistory, ChatHistorySources
from app.modules.tools.pkb.repositories.interfaces.chat_history_repository import IChatHistoryRepository


class ChatHistoryRepository(IChatHistoryRepository):
    """聊天历史仓储实现"""

    def __init__(self, db: AsyncSession):
        """
        初始化聊天历史仓储

        Args:
            db: 数据库会话
        """
        self.db = db

    async def get_by_id_async(self, id: int) -> Optional[ChatHistory]:
        """
        获取聊天历史

        Args:
            id: 聊天历史ID

        Returns:
            聊天历史实体
        """
        result = await self.db.execute(
            select(ChatHistory).where(ChatHistory.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_session_id_async(self, session_id: int, limit: int = 20) -> List[ChatHistory]:
        """
        获取会话的所有聊天历史

        Args:
            session_id: 会话ID
            limit: 数量限制

        Returns:
            聊天历史实体列表
        """
        result = await self.db.execute(
            select(ChatHistory)
            .where(ChatHistory.session_id == session_id)
            .order_by(desc(ChatHistory.create_date))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_paginated_by_session_id_async(
        self, session_id: int, page_size: int = 20, last_id: Optional[int] = None
    ) -> List[ChatHistory]:
        """
        分页获取会话的聊天历史

        Args:
            session_id: 会话ID
            page_size: 每页大小
            last_id: 上次加载的最后一条记录ID，首次加载传None

        Returns:
            聊天历史实体列表
        """
        query = select(ChatHistory).where(ChatHistory.session_id == session_id)

        if last_id:
            # 获取lastId之前的历史记录（向上滚动加载更早的记录）
            query = query.where(ChatHistory.id < last_id)

        # 按ID降序，获取更早的消息
        query = query.order_by(desc(ChatHistory.id)).limit(page_size)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def add_async(self, chat_history: ChatHistory) -> bool:
        """
        新增聊天历史

        Args:
            chat_history: 聊天历史实体

        Returns:
            操作结果
        """
        chat_history.id = generate_id()
        chat_history.create_date = datetime.datetime.now()
        chat_history.last_modify_date = datetime.datetime.now()
        
        self.db.add(chat_history)
        await self.db.flush()
        return True

    async def delete_async(self, id: int) -> bool:
        """
        删除聊天历史

        Args:
            id: 聊天历史ID

        Returns:
            操作结果
        """
        result = await self.db.execute(
            delete(ChatHistory).where(ChatHistory.id == id)
        )
        return result.rowcount > 0

    async def delete_by_session_id_async(self, session_id: int) -> bool:
        """
        删除会话的所有聊天历史

        Args:
            session_id: 会话ID

        Returns:
            操作结果
        """
        result = await self.db.execute(
            delete(ChatHistory).where(ChatHistory.session_id == session_id)
        )
        return result.rowcount > 0

    async def add_history_sources_async(self, chat_history_sources: List[ChatHistorySources]) -> bool:
        """
        新增会话的源数据

        Args:
            chat_history_sources: 会话的源数据

        Returns:
            操作结果
        """
        if not chat_history_sources:
            return True

        # 设置雪花ID、创建和修改时间
        now = datetime.datetime.now()
        for source in chat_history_sources:
            source.id = generate_id()
            source.create_date = now
            source.last_modify_date = now

        # 批量插入
        self.db.add_all(chat_history_sources)
        await self.db.flush()
        return True

    async def get_history_sources_async(self, session_id: int, history_id: int) -> List[ChatHistorySources]:
        """
        获取会话的源数据

        Args:
            session_id: 会话ID
            history_id: 历史记录ID

        Returns:
            会话源数据列表
        """
        result = await self.db.execute(
            select(ChatHistorySources)
            .where(
                and_(
                    ChatHistorySources.session_id == session_id,
                    ChatHistorySources.history_id == history_id
                )
            )
            .order_by(desc(ChatHistorySources.id))
        )
        return list(result.scalars().all())

    async def get_history_sources_by_ids_async(
        self, session_id: int, history_ids: List[int]
    ) -> List[ChatHistorySources]:
        """
        通过历史ID列表获取会话的源数据

        Args:
            session_id: 会话ID
            history_ids: 历史记录ID列表

        Returns:
            会话源数据列表
        """
        result = await self.db.execute(
            select(ChatHistorySources)
            .where(
                and_(
                    ChatHistorySources.session_id == session_id,
                    ChatHistorySources.history_id.in_(history_ids)
                )
            )
            .order_by(desc(ChatHistorySources.id))
        )
        return list(result.scalars().all())