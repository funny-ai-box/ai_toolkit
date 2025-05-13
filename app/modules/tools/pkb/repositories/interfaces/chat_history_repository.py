"""
聊天历史仓储接口
"""
from typing import List, Optional, Protocol
from app.modules.tools.pkb.models import ChatHistory, ChatHistorySources


class IChatHistoryRepository(Protocol):
    """聊天历史仓储接口"""

    async def get_by_id_async(self, id: int) -> Optional[ChatHistory]:
        """
        获取聊天历史

        Args:
            id: 聊天历史ID

        Returns:
            聊天历史实体
        """
        ...

    async def get_by_session_id_async(self, session_id: int, limit: int = 20) -> List[ChatHistory]:
        """
        获取会话的所有聊天历史

        Args:
            session_id: 会话ID
            limit: 数量限制

        Returns:
            聊天历史实体列表
        """
        ...

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
        ...

    async def add_async(self, chat_history: ChatHistory) -> bool:
        """
        新增聊天历史

        Args:
            chat_history: 聊天历史实体

        Returns:
            操作结果
        """
        ...

    async def delete_async(self, id: int) -> bool:
        """
        删除聊天历史

        Args:
            id: 聊天历史ID

        Returns:
            操作结果
        """
        ...

    async def delete_by_session_id_async(self, session_id: int) -> bool:
        """
        删除会话的所有聊天历史

        Args:
            session_id: 会话ID

        Returns:
            操作结果
        """
        ...

    async def add_history_sources_async(self, chat_history_sources: List[ChatHistorySources]) -> bool:
        """
        新增会话的源数据

        Args:
            chat_history_sources: 会话的源数据

        Returns:
            操作结果
        """
        ...

    async def get_history_sources_async(self, session_id: int, history_id: int) -> List[ChatHistorySources]:
        """
        获取会话的源数据

        Args:
            session_id: 会话ID
            history_id: 历史记录ID

        Returns:
            会话源数据列表
        """
        ...

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
        ...