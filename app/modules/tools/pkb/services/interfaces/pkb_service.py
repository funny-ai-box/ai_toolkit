"""
个人知识库服务接口
"""
from typing import List, Optional, Protocol, Tuple, Callable
from app.modules.tools.pkb.dtos.chat_message import ChatMessageDto, ChatReplyDto
from app.modules.tools.pkb.dtos.chat_session import ChatSessionInfoDto
from app.modules.tools.pkb.dtos.share_session import ShareSessionResponseDto


class IPKBService(Protocol):
    """个人知识库服务接口"""

    async def create_chat_session_async(
        self, user_id: int, document_id: int, session_name: str, prompt: Optional[str] = None
    ) -> int:
        """
        创建聊天会话

        Args:
            user_id: 用户ID
            document_id: 文档ID
            session_name: 会话名称
            prompt: 提示词

        Returns:
            会话ID
        """
        ...

    async def update_chat_session_async(
        self, session_id: int, session_name: Optional[str] = None, prompt: Optional[str] = None
    ) -> bool:
        """
        更新聊天会话

        Args:
            session_id: 会话ID
            session_name: 会话名称
            prompt: 提示词

        Returns:
            操作结果
        """
        ...

    async def delete_chat_session_async(self, session_id: int) -> bool:
        """
        删除聊天会话

        Args:
            session_id: 会话ID

        Returns:
            操作结果
        """
        ...

    async def get_user_chat_sessions_async(self, user_id: int) -> List[ChatSessionInfoDto]:
        """
        获取用户的所有聊天会话

        Args:
            user_id: 用户ID

        Returns:
            会话列表
        """
        ...

    async def get_chat_session_detail_async(self, session_id: int) -> Optional[ChatSessionInfoDto]:
        """
        获取聊天会话详情

        Args:
            session_id: 会话ID

        Returns:
            会话详情
        """
        ...

    async def get_chat_history_async(self, session_id: int, limit: int = 20) -> List[ChatMessageDto]:
        """
        获取聊天历史

        Args:
            session_id: 会话ID
            limit: 数量限制

        Returns:
            聊天历史
        """
        ...

    async def get_chat_history_paginated_async(
        self, session_id: int, page_size: int = 20, last_id: Optional[int] = None
    ) -> List[ChatMessageDto]:
        """
        分页获取聊天历史

        Args:
            session_id: 会话ID
            page_size: 每页大小
            last_id: 上次加载的最后一条记录ID，首次加载传None

        Returns:
            聊天历史
        """
        ...

    async def chat_async(self, user_id: int, session_id: int, message: str) -> ChatReplyDto:
        """
        聊天

        Args:
            user_id: 用户ID
            session_id: 会话ID
            message: 用户消息

        Returns:
            AI回复
        """
        ...

    async def streaming_chat_async(
        self, 
        user_id: int, 
        session_id: int, 
        message: str, 
        on_chunk_received: Callable[[str], None],
        cancellation_token = None
    ) -> ChatReplyDto:
        """
        流式聊天

        Args:
            user_id: 用户ID
            session_id: 会话ID
            message: 用户消息
            on_chunk_received: 接收到数据块时的回调函数
            cancellation_token: 取消令牌

        Returns:
            AI回复
        """
        ...

    async def share_session_async(
        self, session_id: int, is_shared: bool, base_url: str
    ) -> ShareSessionResponseDto:
        """
        分享聊天会话

        Args:
            session_id: 会话ID
            is_shared: 是否分享
            base_url: 基础URL

        Returns:
            分享信息
        """
        ...

    async def get_session_by_share_code_async(self, share_code: str) -> Optional[ChatSessionInfoDto]:
        """
        通过分享码获取会话

        Args:
            share_code: 分享码

        Returns:
            会话信息
        """
        ...