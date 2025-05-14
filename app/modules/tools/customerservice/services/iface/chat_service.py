"""
聊天服务接口
"""
from typing import Optional
from fastapi import UploadFile

from app.core.dtos import PagedResultDto
from app.modules.tools.customerservice.services.dtos.chat_dto import (
    ChatSessionDto, ChatSessionListRequestDto, ChatSessionListItemDto,
    ChatHistoryListRequestDto, ChatHistoryDto, ChatMessageRequestDto,
    ChatMessageResultDto
)

class IChatService:
    """智能客服服务接口"""
    
    async def create_session_async(self, user_id: int, user_name: str) -> ChatSessionDto:
        """
        创建会话
        
        Args:
            user_id: 用户ID
            user_name: 用户姓名
            
        Returns:
            会话信息
        """
        raise NotImplementedError()
    
    async def get_session_async(self, user_id: int, session_id: int) -> Optional[ChatSessionDto]:
        """
        获取会话
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            
        Returns:
            会话信息
        """
        raise NotImplementedError()
    
    async def get_session_by_key_async(self, session_key: str) -> Optional[ChatSessionDto]:
        """
        根据会话Key获取会话
        
        Args:
            session_key: 会话Key
            
        Returns:
            会话信息
        """
        raise NotImplementedError()
    
    async def get_user_sessions_async(self, user_id: int, request: ChatSessionListRequestDto) -> PagedResultDto[ChatSessionListItemDto]:
        """
        获取用户的会话列表
        
        Args:
            user_id: 用户ID
            request: 分页请求
            
        Returns:
            分页会话列表
        """
        raise NotImplementedError()
    
    async def end_session_async(self, session_id: int) -> bool:
        """
        结束会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def get_session_history_async(self, user_id: int, request: ChatHistoryListRequestDto) -> PagedResultDto[ChatHistoryDto]:
        """
        获取会话历史记录
        
        Args:
            user_id: 用户ID
            request: 分页请求
            
        Returns:
            分页会话历史记录
        """
        raise NotImplementedError()
    
    async def send_message_async(self, user_id: int, request: ChatMessageRequestDto) -> ChatMessageResultDto:
        """
        发送消息
        
        Args:
            user_id: 用户ID
            request: 消息请求
            
        Returns:
            发送结果
        """
        raise NotImplementedError()
    
    async def send_image_async(self, user_id: int, session_id: int, image: UploadFile) -> ChatMessageResultDto:
        """
        发送图片消息
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            image: 图片文件
            
        Returns:
            发送结果
        """
        raise NotImplementedError()
    
    async def establish_connection_async(self, session_id: int, connection_id: str, client_type: str) -> bool:
        """
        建立实时连接
        
        Args:
            session_id: 会话ID
            connection_id: 连接ID
            client_type: 客户端类型
            
        Returns:
            连接结果
        """
        raise NotImplementedError()
    
    async def close_connection_async(self, connection_id: str) -> bool:
        """
        关闭实时连接
        
        Args:
            connection_id: 连接ID
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def keep_connection_alive_async(self, connection_id: str) -> bool:
        """
        更新连接活跃状态
        
        Args:
            connection_id: 连接ID
            
        Returns:
            操作结果
        """
        raise NotImplementedError()