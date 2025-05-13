"""
原型消息服务，处理聊天消息的获取和处理
"""
import logging
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dtos import PagedResultDto
from app.core.exceptions import ForbiddenException, BusinessException
from app.modules.tools.prototype.dtos import MessageDto, MessageListRequestDto
from app.modules.tools.prototype.enums import PrototypeMessageType
from app.modules.tools.prototype.repositories import PrototypeSessionRepository, PrototypeMessageRepository


class PrototypeMessageService:
    """原型消息服务实现"""
    
    def __init__(
        self,
        db: AsyncSession,
        session_repository: PrototypeSessionRepository,
        message_repository: PrototypeMessageRepository,
        logger: logging.Logger
    ):
        """
        初始化消息服务
        
        Args:
            db: 数据库会话
            session_repository: 会话仓储
            message_repository: 消息仓储
            logger: 日志记录器
        """
        self.db = db
        self.session_repository = session_repository
        self.message_repository = message_repository
        self.logger = logger
    
    async def get_session_messages_async(self, user_id: int, session_id: int) -> List[MessageDto]:
        """
        获取会话的所有消息
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            
        Returns:
            消息列表
        """
        try:
            # 检查用户权限
            session = await self.session_repository.get_by_id_async(session_id)
            if session is None or session.user_id != user_id:
                raise ForbiddenException("无权访问该会话")
            
            messages = await self.message_repository.get_by_session_id_async(session_id)
            return [
                MessageDto(
                    id=m.id,
                    sessionId=m.session_id,
                    messageType=m.message_type,
                    messageTypeDescription=self._get_message_type_description(m.message_type),
                    content=m.content,
                    isCode=m.is_code,
                    attachmentIds=m.attachment_ids,
                    attachmentUrls=m.attachment_urls,
                    createDate=m.create_date
                )
                for m in messages
            ]
        except Exception as ex:
            if not isinstance(ex, ForbiddenException):
                self.logger.error(f"获取会话消息失败，会话ID: {session_id}", exc_info=ex)
                raise BusinessException(f"获取会话消息失败: {str(ex)}")
            raise
    
    async def get_session_messages_paged_async(self, user_id: int, request: MessageListRequestDto) -> PagedResultDto[MessageDto]:
        """
        分页获取会话的消息
        
        Args:
            user_id: 用户ID
            request: 消息列表请求
            
        Returns:
            消息分页结果
        """
        try:
            # 检查用户权限
            session = await self.session_repository.get_by_id_async(request.session_id)
            if session is None or session.user_id != user_id:
                raise ForbiddenException("无权访问该会话")
            
            messages, total_count = await self.message_repository.get_paginated_async(
                request.session_id, request.page_index, request.page_size)
            
            # 转换为DTO列表
            items = [
                MessageDto(
                    id=m.id,
                    sessionId=m.session_id,
                    messageType=m.message_type,
                    messageTypeDescription=self._get_message_type_description(m.message_type),
                    content=m.content,
                    isCode=m.is_code,
                    attachmentIds=m.attachment_ids,
                    attachmentUrls=m.attachment_urls,
                    createDate=m.create_date
                )
                for m in messages
            ]
            
            # 构建分页结果
            return PagedResultDto[MessageDto](
                items=items,
                totalCount=total_count,
                pageIndex=request.page_index,
                pageSize=request.page_size,
                totalPages=(total_count + request.page_size - 1) // request.page_size
            )
        except Exception as ex:
            if not isinstance(ex, ForbiddenException):
                self.logger.error(f"分页获取会话消息失败，会话ID: {request.session_id}", exc_info=ex)
                raise BusinessException(f"获取会话消息失败: {str(ex)}")
            raise
    
    def _get_message_type_description(self, message_type: PrototypeMessageType) -> str:
        """
        获取消息类型描述
        
        Args:
            message_type: 消息类型
            
        Returns:
            消息类型描述
        """
        if message_type == PrototypeMessageType.USER:
            return "用户"
        elif message_type == PrototypeMessageType.AI:
            return "AI"
        elif message_type == PrototypeMessageType.SYSTEM:
            return "系统"
        else:
            return "未知"