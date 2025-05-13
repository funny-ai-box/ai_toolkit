"""
个人知识库服务实现
"""
import logging
from typing import List, Optional, Callable, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import Settings
from app.core.exceptions import BusinessException
from app.core.dtos import DocumentAppType
from app.core.ai.dtos import UserDocsVectorSearchResult

from app.modules.base.knowledge.repositories.document_repository import DocumentRepository
from app.modules.tools.pkb.dtos.chat_message import ChatMessageDto, ChatReplyDto, SourceReferenceDto
from app.modules.tools.pkb.dtos.chat_session import ChatSessionInfoDto
from app.modules.tools.pkb.dtos.share_session import ShareSessionResponseDto
from app.modules.tools.pkb.services.interfaces.pkb_service import IPKBService
from app.modules.tools.pkb.services.chat_service import ChatService


logger = logging.getLogger(__name__)


class PKBService(IPKBService):
    """个人知识库服务实现"""

    def __init__(
        self,
        db: AsyncSession,
        settings: Settings,
        chat_service: ChatService,
        document_repository: DocumentRepository
    ):
        """
        初始化个人知识库服务

        Args:
            db: 数据库会话
            settings: 配置
            chat_service: 聊天服务
            document_repository: 文档仓储
        """
        self.db = db
        self.settings = settings
        self.chat_service = chat_service
        self.document_repository = document_repository

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
        return await self.chat_service.create_session_async(user_id, document_id, session_name, prompt)

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
        return await self.chat_service.update_session_async(session_id, session_name, prompt)

    async def delete_chat_session_async(self, session_id: int) -> bool:
        """
        删除聊天会话

        Args:
            session_id: 会话ID

        Returns:
            操作结果
        """
        return await self.chat_service.delete_session_async(session_id)

    async def get_user_chat_sessions_async(self, user_id: int) -> List[ChatSessionInfoDto]:
        """
        获取用户的所有聊天会话

        Args:
            user_id: 用户ID

        Returns:
            会话列表
        """
        sessions = await self.chat_service.chat_session_repository.get_by_user_id_async(user_id)
        return [
            ChatSessionInfoDto(
                id=s.id,
                document_id=s.document_id,
                session_name=s.session_name,
                share_code=s.share_code,
                is_shared=s.is_shared,
                prompt=s.prompt,
                create_date=s.create_date,
                last_modify_date=s.last_modify_date
            )
            for s in sessions
        ]

    async def get_chat_session_detail_async(self, session_id: int) -> Optional[ChatSessionInfoDto]:
        """
        获取聊天会话详情

        Args:
            session_id: 会话ID

        Returns:
            会话详情
        """
        session = await self.chat_service.chat_session_repository.get_by_id_async(session_id)
        if not session:
            raise BusinessException(f"会话{session_id}不存在")

        return ChatSessionInfoDto(
            id=session.id,
            document_id=session.document_id,
            session_name=session.session_name,
            share_code=session.share_code,
            is_shared=session.is_shared,
            prompt=session.prompt,
            create_date=session.create_date,
            last_modify_date=session.last_modify_date
        )

    async def get_chat_history_async(self, session_id: int, limit: int = 20) -> List[ChatMessageDto]:
        """
        获取聊天历史

        Args:
            session_id: 会话ID
            limit: 数量限制

        Returns:
            聊天历史
        """
        history = await self.chat_service.get_session_history_async(session_id, limit)
        return [
            ChatMessageDto(
                id=h.id,
                session_id=h.session_id,
                role=h.role,
                content=h.content,
                create_date=h.create_date
            )
            for h in history
        ]

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
        histories = await self.chat_service.chat_history_repository.get_paginated_by_session_id_async(
            session_id, page_size, last_id
        )
        
        results = []
        if histories:
            # 获取所有历史记录的ID列表，用于批量获取引用源
            history_ids = [h.id for h in histories]
            
            # 批量获取引用源
            sources = await self.chat_service.chat_history_repository.get_history_sources_by_ids_async(
                session_id, history_ids
            )
            
            # 按历史记录ID组织引用源
            source_map = {}
            for source in sources:
                if source.history_id not in source_map:
                    source_map[source.history_id] = []
                source_map[source.history_id].append(source)
            
            # 构建返回结果
            for history in histories:
                source_references = []
                if history.id in source_map:
                    source_references = [
                        SourceReferenceDto(
                            document_id=s.document_id,
                            document_title=s.document_title,
                            content=s.content,
                            score=s.score
                        )
                        for s in source_map[history.id]
                    ]
                
                results.append(
                    ChatMessageDto(
                        id=history.id,
                        session_id=history.session_id,
                        role=history.role,
                        content=history.content,
                        sources=source_references,
                        create_date=history.create_date
                    )
                )
        
        return results

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
        reply, reply_message_id, search_results = await self.chat_service.chat_async(
            user_id, session_id, message
        )
        
        # 构建回复DTO
        chat_reply = await self._build_chat_reply(session_id, reply, reply_message_id, search_results)
        return chat_reply

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
        reply, reply_message_id, search_results = await self.chat_service.streaming_chat_async(
            user_id, session_id, message, on_chunk_received, cancellation_token
        )
        
        # 构建回复DTO
        chat_reply = await self._build_chat_reply(session_id, reply, reply_message_id, search_results)
        return chat_reply

    async def _build_chat_reply(
        self, session_id: int, reply: str, reply_message_id: int, search_results: List[UserDocsVectorSearchResult]
    ) -> ChatReplyDto:
        """
        构建聊天回复DTO

        Args:
            session_id: 会话ID
            reply: 回复内容
            reply_message_id: 回复消息ID
            search_results: 搜索结果

        Returns:
            ChatReplyDto
        """
        # 获取文档信息
        document_ids = list(set(s.document_id for s in search_results))
        documents = await self.document_repository.get_by_ids_async(document_ids) if document_ids else []
        
        # 构建文档ID到文档标题的映射
        document_dict = {d.id: d for d in documents}
        
        # 构建来源引用列表
        MAX_CONTENT_LENGTH = 100  # 每个引用的最大内容长度
        source_references = []
        
        for result in search_results:
            document_title = "未知文档"
            if result.document_id in document_dict:
                document_title = document_dict[result.document_id].title or "未知文档"
            
            source_references.append(
                SourceReferenceDto(
                    document_id=result.document_id,
                    document_title=document_title,
                    content=self._truncate_content(result.content, MAX_CONTENT_LENGTH),
                    score=result.score
                )
            )
        
        # 如果有引用源，保存到数据库
        if source_references:
            from app.modules.tools.pkb.models import ChatHistorySources
            
            history_sources = [
                ChatHistorySources(
                    session_id=session_id,
                    history_id=reply_message_id,
                    document_id=source.document_id,
                    document_title=source.document_title,
                    content=source.content,
                    score=source.score
                )
                for source in source_references
            ]
            
            await self.chat_service.chat_history_repository.add_history_sources_async(history_sources)
        
        # 返回聊天回复DTO
        return ChatReplyDto(
            reply=reply,
            sources=source_references
        )

    def _truncate_content(self, content: str, max_length: int) -> str:
        """
        截断内容文本，保留完整句子

        Args:
            content: 原始内容
            max_length: 最大长度

        Returns:
            截断后的内容
        """
        if not content or len(content) <= max_length:
            return content

        # 尝试在句子结束处截断
        pos = max_length
        sentence_endings = ['.', '?', '!', '。', '？', '！']

        # 向前查找最近的句子结束符
        while pos > max_length // 2:
            if content[pos] in sentence_endings:
                return content[:pos + 1] + "..."
            pos -= 1

        # 如果没有找到合适的句子结束，则在词语处截断
        pos = max_length
        while pos > 0:
            if content[pos].isspace():
                return content[:pos] + "..."
            pos -= 1

        # 最后的方案：直接在maxLength处截断
        return content[:max_length] + "..."

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
        share_code = await self.chat_service.share_session_async(session_id, is_shared)
        
        if not share_code:
            return ShareSessionResponseDto(
                share_code="",
                share_url=""
            )
        
        share_url = f"{base_url}/pkb/share/{share_code}"
        
        return ShareSessionResponseDto(
            share_code=share_code,
            share_url=share_url
        )

    async def get_session_by_share_code_async(self, share_code: str) -> Optional[ChatSessionInfoDto]:
        """
        通过分享码获取会话

        Args:
            share_code: 分享码

        Returns:
            会话信息
        """
        session = await self.chat_service.get_session_by_share_code_async(share_code)
        if not session:
            raise BusinessException(f"分享的会话不存在或已取消分享")
        
        return ChatSessionInfoDto(
            id=session.id,
            document_id=session.document_id,
            session_name=session.session_name,
            share_code=session.share_code,
            is_shared=session.is_shared,
            prompt=session.prompt,
            create_date=session.create_date,
            last_modify_date=session.last_modify_date
        )