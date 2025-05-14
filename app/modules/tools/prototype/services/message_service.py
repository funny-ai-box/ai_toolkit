# app/modules/tools/prototype/services/message_service.py
from typing import List, Optional
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dtos import PagedResultDto
from app.core.exceptions import BusinessException, ForbiddenException
from app.modules.tools.prototype.constants import PrototypeMessageType
from app.modules.tools.prototype.dtos import MessageListRequestDto, MessageDto
from app.modules.tools.prototype.repositories import (
    PrototypeSessionRepository, PrototypeMessageRepository
)


class PrototypeMessageService:
    """原型消息服务实现"""
    
    def __init__(
        self,
        db: AsyncSession,
        session_repository: PrototypeSessionRepository,
        message_repository: PrototypeMessageRepository,
        logger: Optional[logging.Logger] = None
    ):
        """
        初始化
        
        Args:
            db: 数据库会话
            session_repository: 会话仓储
            message_repository: 消息仓储
            logger: 日志记录器
        """
        self.db = db
        self.session_repository = session_repository
        self.message_repository = message_repository
        self.logger = logger or logging.getLogger(__name__)
    
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
                    session_id=m.session_id,
                    message_type=m.message_type,
                    message_type_description=self._get_message_type_description(m.message_type),
                    content=m.content,
                    is_code=m.is_code,
                    attachment_ids=m.attachment_ids,
                    attachment_urls=m.attachment_urls,
                    create_date=m.create_date
                )
                for m in messages
            ]
            
        except Exception as ex:
            if isinstance(ex, ForbiddenException):
                raise
            
            self.logger.error(f"获取会话消息失败，会话ID: {session_id}: {str(ex)}")
            raise BusinessException(f"获取会话消息失败: {str(ex)}")
    
    async def get_session_messages_paged_async(
        self, user_id: int, request: MessageListRequestDto
    ) -> PagedResultDto[MessageDto]:
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
                request.session_id, request.page_index, request.page_size
            )
            
            # 转换为DTO列表
            items = [
                MessageDto(
                    id=m.id,
                    session_id=m.session_id,
                    message_type=m.message_type,
                    message_type_description=self._get_message_type_description(m.message_type),
                    content=m.content,
                    is_code=m.is_code,
                    attachment_ids=m.attachment_ids,
                    attachment_urls=m.attachment_urls,
                    create_date=m.create_date
                )
                for m in messages
            ]
            
            # 构建分页结果
            result = PagedResultDto[MessageDto](
                items=items,
                total_count=total_count,
                page_index=request.page_index,
                page_size=request.page_size,
                total_pages=(total_count + request.page_size - 1) // request.page_size
            )
            
            return result
            
        except Exception as ex:
            if isinstance(ex, ForbiddenException):
                raise
            
            self.logger.error(f"分页获取会话消息失败，会话ID: {request.session_id}: {str(ex)}")
            raise BusinessException(f"获取会话消息失败: {str(ex)}")
    
    def _get_message_type_description(self, message_type: PrototypeMessageType) -> str:
        """
        获取消息类型描述
        
        Args:
            message_type: 消息类型
            
        Returns:
            消息类型描述
        """
        message_type_descriptions = {
            PrototypeMessageType.USER: "用户",
            PrototypeMessageType.AI: "AI",
            PrototypeMessageType.SYSTEM: "系统"
        }
        return message_type_descriptions.get(message_type, "未知")