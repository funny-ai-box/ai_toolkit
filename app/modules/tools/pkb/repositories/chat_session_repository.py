"""
聊天会话仓储实现
"""
import datetime
from typing import List, Optional
from sqlalchemy import select, delete, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.snowflake import generate_id
from app.modules.tools.pkb.models import ChatSession
from app.modules.tools.pkb.repositories.interfaces.chat_session_repository import IChatSessionRepository


class ChatSessionRepository(IChatSessionRepository):
    """聊天会话仓储实现"""

    def __init__(self, db: AsyncSession):
        """
        初始化聊天会话仓储

        Args:
            db: 数据库会话
        """
        self.db = db

    async def get_by_id_async(self, id: int) -> Optional[ChatSession]:
        """
        获取聊天会话

        Args:
            id: 聊天会话ID

        Returns:
            聊天会话实体
        """
        result = await self.db.execute(
            select(ChatSession).where(ChatSession.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id_async(self, user_id: int) -> List[ChatSession]:
        """
        获取用户的所有聊天会话

        Args:
            user_id: 用户ID

        Returns:
            聊天会话实体列表
        """
        result = await self.db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(desc(ChatSession.last_modify_date))
        )
        return list(result.scalars().all())

    async def add_async(self, chat_session: ChatSession) -> bool:
        """
        新增聊天会话

        Args:
            chat_session: 聊天会话实体

        Returns:
            操作结果
        """
        chat_session.id = generate_id()
        chat_session.create_date = datetime.datetime.now()
        chat_session.last_modify_date = datetime.datetime.now()
        
        self.db.add(chat_session)
        await self.db.flush()
        return True

    async def update_async(self, chat_session: ChatSession) -> bool:
        """
        更新聊天会话

        Args:
            chat_session: 聊天会话实体

        Returns:
            操作结果
        """
        chat_session.last_modify_date = datetime.datetime.now()
        await self.db.merge(chat_session)
        await self.db.flush()
        return True

    async def delete_async(self, id: int) -> bool:
        """
        删除聊天会话

        Args:
            id: 聊天会话ID

        Returns:
            操作结果
        """
        result = await self.db.execute(
            delete(ChatSession).where(ChatSession.id == id)
        )
        return result.rowcount > 0

    async def get_by_share_code_async(self, share_code: str) -> Optional[ChatSession]:
        """
        通过分享码获取聊天会话

        Args:
            share_code: 分享码

        Returns:
            聊天会话实体
        """
        result = await self.db.execute(
            select(ChatSession).where(
                and_(
                    ChatSession.share_code == share_code,
                    ChatSession.is_shared == True
                )
            )
        )
        return result.scalar_one_or_none()