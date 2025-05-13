"""
聊天会话仓储接口
"""
from typing import List, Optional, Protocol
from app.modules.tools.pkb.models import ChatSession


class IChatSessionRepository(Protocol):
    """聊天会话仓储接口"""

    async def get_by_id_async(self, id: int) -> Optional[ChatSession]:
        """
        获取聊天会话

        Args:
            id: 聊天会话ID

        Returns:
            聊天会话实体
        """
        ...

    async def get_by_user_id_async(self, user_id: int) -> List[ChatSession]:
        """
        获取用户的所有聊天会话

        Args:
            user_id: 用户ID

        Returns:
            聊天会话实体列表
        """
        ...

    async def add_async(self, chat_session: ChatSession) -> bool:
        """
        新增聊天会话

        Args:
            chat_session: 聊天会话实体

        Returns:
            操作结果
        """
        ...

    async def update_async(self, chat_session: ChatSession) -> bool:
        """
        更新聊天会话

        Args:
            chat_session: 聊天会话实体

        Returns:
            操作结果
        """
        ...

    async def delete_async(self, id: int) -> bool:
        """
        删除聊天会话

        Args:
            id: 聊天会话ID

        Returns:
            操作结果
        """
        ...

    async def get_by_share_code_async(self, share_code: str) -> Optional[ChatSession]:
        """
        通过分享码获取聊天会话

        Args:
            share_code: 分享码

        Returns:
            聊天会话实体
        """
        ...